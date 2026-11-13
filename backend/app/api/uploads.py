"""Dosya yükleme güvenliği.

Kurallar
--------
1. **Yalnızca ``.xlsx``.** Uzantı kontrolü tek başına yetmez: dosyanın
   gerçekten bir OOXML paketi (ZIP) olduğu ilk baytlardan doğrulanır.
2. **Boyut sınırı.** Akış parça parça okunur; sınır aşılırsa okuma kesilir,
   dosya diske tamamen yazılmaz. Belleğe tam dosya alınmaz.
3. **İstemci dosya adı diske yazılmaz.** Geçici dosya sunucunun seçtiği sabit
   bir adla oluşturulur; istemci adı yalnızca uzantı denetiminde kullanılır ve
   log'a da yazılmaz (kontrol karakteri/path traversal riski).
4. **Geçici dosya her durumda silinir.** :class:`UploadWorkspace` bağlam
   yöneticisi hata durumunda da temizler.
"""

from __future__ import annotations

import tempfile
from contextlib import AbstractContextManager
from pathlib import Path

from fastapi import UploadFile

from app.api.errors import ApiError
from app.config import DEFAULT_MAX_UPLOAD_BYTES

#: Okuma parçası boyu.
_CHUNK_SIZE = 64 * 1024

#: OOXML paketlerinin (ve tüm ZIP dosyalarının) imzası.
_ZIP_MAGIC = b"PK\x03\x04"

#: Sunucunun geçici dosyaya verdiği sabit ad. İstemci adı kullanılmaz.
_TEMP_FILENAME = "metraj.xlsx"


class UploadWorkspace(AbstractContextManager["UploadWorkspace"]):
    """Yükleme için geçici dizin; çıkışta **her durumda** silinir."""

    def __init__(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="buildflow-metraj-")
        self.path = Path(self._directory.name) / _TEMP_FILENAME

    def __enter__(self) -> "UploadWorkspace":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._directory.cleanup()


def _client_extension(filename: str | None) -> str:
    """İstemci dosya adından **yalnızca** uzantıyı çıkarır.

    Ad hiçbir yerde saklanmaz veya yansıtılmaz; yalnızca uzantı karşılaştırılır.
    """
    if not filename:
        return ""
    # Yol ayırıcıları ve kontrol karakterleri atılır: `../../x.xlsx` gibi
    # girişler yalnızca ".xlsx" uzantısı olarak değerlendirilir.
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(character for character in name if character.isprintable())
    return Path(name).suffix.lower()[:16]


def _reject_format(extension: str) -> ApiError:
    shown = extension or "(uzantısız)"
    return ApiError(
        415,
        "unsupported-format",
        f"Desteklenmeyen dosya biçimi: {shown}",
        detail=f"Yalnızca .xlsx dosyaları okunur (gönderilen: {shown}).",
        suggestion=(
            "Dosyayı Excel'de 'Excel Çalışma Kitabı (*.xlsx)' olarak kaydedip "
            "yeniden yükleyin. .xls, .xlsm ve .csv desteklenmez."
        ),
    )


async def _stream_to_disk(upload: UploadFile, target: Path, max_bytes: int) -> int:
    written = 0
    try:
        with target.open("wb") as handle:
            while True:
                chunk = await upload.read(_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise ApiError(
                        413,
                        "file-too-large",
                        "Dosya boyutu sınırı aşıldı.",
                        detail=(
                            f"İzin verilen en büyük dosya "
                            f"{max_bytes // (1024 * 1024)} MB."
                        ),
                        suggestion=(
                            "Gereksiz sayfaları/kolonları kaldırın veya dosyayı "
                            "bölerek yükleyin."
                        ),
                    )
                handle.write(chunk)
    except ApiError:
        target.unlink(missing_ok=True)
        raise
    except OSError as exc:  # pragma: no cover - disk hatası
        target.unlink(missing_ok=True)
        raise ApiError(
            500,
            "upload-failed",
            "Dosya kaydedilemedi.",
            suggestion="Lütfen daha sonra tekrar deneyin.",
        ) from exc

    if written == 0:
        target.unlink(missing_ok=True)
        raise ApiError(
            422,
            "empty-file",
            "Boş dosya yüklendi.",
            suggestion="Dolu bir .xlsx metraj dosyası seçin.",
        )
    return written


def _assert_real_xlsx(path: Path) -> None:
    """Uzantıya ek olarak dosyanın gerçek bir OOXML paketi olduğunu doğrular."""
    try:
        with path.open("rb") as handle:
            header = handle.read(4)
    except OSError as exc:  # pragma: no cover - okuma hatası
        raise ApiError(
            422,
            "corrupt-file",
            "Dosya okunamadı.",
            suggestion="Dosyayı yeniden kaydedip tekrar yükleyin.",
        ) from exc

    if header != _ZIP_MAGIC:
        raise ApiError(
            422,
            "corrupt-file",
            "Dosya geçerli bir Excel çalışma kitabı değil.",
            detail=(
                "Dosya imzası OOXML paketiyle uyuşmuyor. Uzantı .xlsx olsa da "
                "içerik Excel dosyası değil."
            ),
            suggestion=(
                "Dosyayı Excel'de açıp '.xlsx' olarak yeniden kaydedin. "
                "Yeniden adlandırılmış dosyalar (ör. .csv → .xlsx) okunamaz."
            ),
        )


async def receive_upload(
    workspace: UploadWorkspace,
    upload: UploadFile,
    *,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> Path:
    """Yüklemeyi doğrular ve geçici dosyaya yazar; yolu döndürür."""
    extension = _client_extension(upload.filename)
    if extension != ".xlsx":
        raise _reject_format(extension)

    await _stream_to_disk(upload, workspace.path, max_bytes)
    _assert_real_xlsx(workspace.path)
    return workspace.path
