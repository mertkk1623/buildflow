/**
 * Örnek proje metrajının **gerçek backend çıktısı** — elle yazılmamıştır.
 *
 * Kaynak: `templates/proje_ornek_metraj.xlsx` (40 satır) → `/api/analyze`.
 * Satırlar, mesajlar ve adaylar sunucunun ürettiği JSON'dan birebir
 * kopyalanmıştır; arayüz bu sözleşmeyle test edilir.
 *
 * Yeniden üretmek için `backend/tools/make_sample_fixtures.py` çalıştırılır.
 */

import type { AnalyzeResponse } from '../../types/api'

/** 40 satır: 32 kural, 5 onay bekleyen, 3 kapsam dışı. */
export const SAMPLE_ANALYSIS: AnalyzeResponse = {
  "rows": [
    {
      "source_row": 2,
      "boq_no": "STR-001",
      "description": "A Blok kolon — kutu profil 60×60×3 S235 siyah",
      "quantity": "540",
      "unit": "m",
      "waste_percent": "6",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-60-60-3-S235-B",
        "candidate_codes": [
          "BOX-60-60-3-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-60-60-3-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "60×60×3",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 60×60×3 · S235 · siyah",
            "mass_kg_per_m": "5.19",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 3,
      "boq_no": "STR-002",
      "description": "A Blok kolon — kutu profil 60×60×3 S235 siyah",
      "quantity": "1.86",
      "unit": "t",
      "waste_percent": "6",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-60-60-3-S235-B",
        "candidate_codes": [
          "BOX-60-60-3-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-60-60-3-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "60×60×3",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 60×60×3 · S235 · siyah",
            "mass_kg_per_m": "5.19",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 4,
      "boq_no": "STR-003",
      "description": "B Blok kiriş — kutu profil 80×80×3 S235 siyah",
      "quantity": "320",
      "unit": "m",
      "waste_percent": "5",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-80-80-3-S235-B",
        "candidate_codes": [
          "BOX-80-80-3-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-80-80-3-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "80×80×3",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 80×80×3 · S235 · siyah",
            "mass_kg_per_m": "7.07",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 5,
      "boq_no": "STR-004",
      "description": "Konsol kirişi — kutu profil 80×80×3 S235 siyah",
      "quantity": "96",
      "unit": "m",
      "waste_percent": "8",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-80-80-3-S235-B",
        "candidate_codes": [
          "BOX-80-80-3-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-80-80-3-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "80×80×3",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 80×80×3 · S235 · siyah",
            "mass_kg_per_m": "7.07",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 6,
      "boq_no": "STR-005",
      "description": "Ana kiriş — kutu profil 100×100×4 S235 siyah",
      "quantity": "480",
      "unit": "m",
      "waste_percent": "5",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-100-4-S235-B",
        "candidate_codes": [
          "BOX-100-4-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-100-4-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "100×100×4",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 100×100×4 · S235 · siyah",
            "mass_kg_per_m": "11.70",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 7,
      "boq_no": "STR-006",
      "description": "Ana kiriş — kutu profil 100×100×4 S235 siyah",
      "quantity": "2240",
      "unit": "kg",
      "waste_percent": "12",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-100-4-S235-B",
        "candidate_codes": [
          "BOX-100-4-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-100-4-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "100×100×4",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 100×100×4 · S235 · siyah",
            "mass_kg_per_m": "11.70",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 8,
      "boq_no": "STR-007",
      "description": "Tali kiriş — kutu profil 100×100×4 S235 siyah",
      "quantity": "540",
      "unit": "m",
      "waste_percent": "5",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-100-4-S235-B",
        "candidate_codes": [
          "BOX-100-4-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-100-4-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "100×100×4",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 100×100×4 · S235 · siyah",
            "mass_kg_per_m": "11.70",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 9,
      "boq_no": "CEP-001",
      "description": "Cephe kaplaması — kutu profil 100×100×4 S235 galvaniz",
      "quantity": "260",
      "unit": "m",
      "waste_percent": "7",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-100-4-S235-G",
        "candidate_codes": [
          "BOX-100-4-S235-G"
        ],
        "candidates": [
          {
            "code": "BOX-100-4-S235-G",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "100×100×4",
            "grade": "S235",
            "coating": "galvaniz",
            "label": "Kutu profil 100×100×4 · S235 · galvaniz",
            "mass_kg_per_m": "11.70",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 10,
      "boq_no": "CEP-002",
      "description": "Cephe kaplaması — kutu profil 100×100×4 S235 galvaniz",
      "quantity": "1.2",
      "unit": "t",
      "waste_percent": "7",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-100-4-S235-G",
        "candidate_codes": [
          "BOX-100-4-S235-G"
        ],
        "candidates": [
          {
            "code": "BOX-100-4-S235-G",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "100×100×4",
            "grade": "S235",
            "coating": "galvaniz",
            "label": "Kutu profil 100×100×4 · S235 · galvaniz",
            "mass_kg_per_m": "11.70",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 11,
      "boq_no": "CEP-003",
      "description": "Merdiven korkuluğu — kutu profil 100×100×4 S235 galvaniz",
      "quantity": "84",
      "unit": "m",
      "waste_percent": "10",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-100-4-S235-G",
        "candidate_codes": [
          "BOX-100-4-S235-G"
        ],
        "candidates": [
          {
            "code": "BOX-100-4-S235-G",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "100×100×4",
            "grade": "S235",
            "coating": "galvaniz",
            "label": "Kutu profil 100×100×4 · S235 · galvaniz",
            "mass_kg_per_m": "11.70",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 12,
      "boq_no": "STR-008",
      "description": "Makas alt başlığı — kutu profil 150×100×5 S235 siyah",
      "quantity": "240",
      "unit": "m",
      "waste_percent": "6",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-150-100-5-S235-B",
        "candidate_codes": [
          "BOX-150-100-5-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-150-100-5-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "150×100×5",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 150×100×5 · S235 · siyah",
            "mass_kg_per_m": "18.30",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 13,
      "boq_no": "STR-009",
      "description": "Makas üst başlığı — kutu profil 150×100×5 S235 siyah",
      "quantity": "240",
      "unit": "m",
      "waste_percent": "6",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "BOX-150-100-5-S235-B",
        "candidate_codes": [
          "BOX-150-100-5-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-150-100-5-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "150×100×5",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 150×100×5 · S235 · siyah",
            "mass_kg_per_m": "18.30",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 14,
      "boq_no": "STR-010",
      "description": "Makas alt başlığı — IPE 200 S235 siyah",
      "quantity": "120",
      "unit": "m",
      "waste_percent": "4",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "IPE-200-S235",
        "candidate_codes": [
          "IPE-200-S235"
        ],
        "candidates": [
          {
            "code": "IPE-200-S235",
            "family": "IPE",
            "family_label": "IPE",
            "size": "200",
            "grade": "S235",
            "coating": "siyah",
            "label": "IPE 200 · S235 · siyah",
            "mass_kg_per_m": "22.40",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 15,
      "boq_no": "STR-011",
      "description": "Makas üst başlığı — IPE 200 S235 siyah",
      "quantity": "116",
      "unit": "m",
      "waste_percent": "4",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "IPE-200-S235",
        "candidate_codes": [
          "IPE-200-S235"
        ],
        "candidates": [
          {
            "code": "IPE-200-S235",
            "family": "IPE",
            "family_label": "IPE",
            "size": "200",
            "grade": "S235",
            "coating": "siyah",
            "label": "IPE 200 · S235 · siyah",
            "mass_kg_per_m": "22.40",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 16,
      "boq_no": "STR-012",
      "description": "Kritik yol — çatı makası IPE 200",
      "quantity": "2800",
      "unit": "kg",
      "waste_percent": "5",
      "status": "pending",
      "match": {
        "status": "pending",
        "matched_code": null,
        "candidate_codes": [
          "IPE-200-S235"
        ],
        "candidates": [
          {
            "code": "IPE-200-S235",
            "family": "IPE",
            "family_label": "IPE",
            "size": "200",
            "grade": "S235",
            "coating": "siyah",
            "label": "IPE 200 · S235 · siyah",
            "mass_kg_per_m": "22.40",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Eksik özellik(ler): kalite, kaplama. Otomatik eşleştirme yapılmaz; kullanıcı onayı gerekir."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 17,
      "boq_no": "STR-013",
      "description": "Kolon gövdesi — IPE 240 S355 siyah",
      "quantity": "4.8",
      "unit": "t",
      "waste_percent": "4",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "IPE-240-S355",
        "candidate_codes": [
          "IPE-240-S355"
        ],
        "candidates": [
          {
            "code": "IPE-240-S355",
            "family": "IPE",
            "family_label": "IPE",
            "size": "240",
            "grade": "S355",
            "coating": "siyah",
            "label": "IPE 240 · S355 · siyah",
            "mass_kg_per_m": "30.70",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 18,
      "boq_no": "STR-014",
      "description": "Kiriş gövdesi — IPE 240 S355 siyah",
      "quantity": "2150",
      "unit": "kg",
      "waste_percent": "4",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "IPE-240-S355",
        "candidate_codes": [
          "IPE-240-S355"
        ],
        "candidates": [
          {
            "code": "IPE-240-S355",
            "family": "IPE",
            "family_label": "IPE",
            "size": "240",
            "grade": "S355",
            "coating": "siyah",
            "label": "IPE 240 · S355 · siyah",
            "mass_kg_per_m": "30.70",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 19,
      "boq_no": "STR-015",
      "description": "Tali kiriş — IPE 240",
      "quantity": "1.4",
      "unit": "t",
      "waste_percent": "4",
      "status": "pending",
      "match": {
        "status": "pending",
        "matched_code": null,
        "candidate_codes": [
          "IPE-240-S355"
        ],
        "candidates": [
          {
            "code": "IPE-240-S355",
            "family": "IPE",
            "family_label": "IPE",
            "size": "240",
            "grade": "S355",
            "coating": "siyah",
            "label": "IPE 240 · S355 · siyah",
            "mass_kg_per_m": "30.70",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Eksik özellik(ler): kalite, kaplama. Otomatik eşleştirme yapılmaz; kullanıcı onayı gerekir."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 20,
      "boq_no": "STR-016",
      "description": "A Blok kolon — HEA 160 S235 siyah",
      "quantity": "288",
      "unit": "m",
      "waste_percent": "5",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "HEA-160-S235",
        "candidate_codes": [
          "HEA-160-S235"
        ],
        "candidates": [
          {
            "code": "HEA-160-S235",
            "family": "HEA",
            "family_label": "HEA",
            "size": "160",
            "grade": "S235",
            "coating": "siyah",
            "label": "HEA 160 · S235 · siyah",
            "mass_kg_per_m": "30.40",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 21,
      "boq_no": "STR-017",
      "description": "B Blok kolon — HEA 160 S235 siyah",
      "quantity": "1.9",
      "unit": "t",
      "waste_percent": "5",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "HEA-160-S235",
        "candidate_codes": [
          "HEA-160-S235"
        ],
        "candidates": [
          {
            "code": "HEA-160-S235",
            "family": "HEA",
            "family_label": "HEA",
            "size": "160",
            "grade": "S235",
            "coating": "siyah",
            "label": "HEA 160 · S235 · siyah",
            "mass_kg_per_m": "30.40",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 22,
      "boq_no": "STR-018",
      "description": "Ana kiriş — HEA 200 S235 siyah",
      "quantity": "216",
      "unit": "m",
      "waste_percent": "5",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "HEA-200-S235",
        "candidate_codes": [
          "HEA-200-S235"
        ],
        "candidates": [
          {
            "code": "HEA-200-S235",
            "family": "HEA",
            "family_label": "HEA",
            "size": "200",
            "grade": "S235",
            "coating": "siyah",
            "label": "HEA 200 · S235 · siyah",
            "mass_kg_per_m": "42.30",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 23,
      "boq_no": "CEP-008",
      "description": "Cephe kirişi — HEA 200 S235 siyah",
      "quantity": "900",
      "unit": "kg",
      "waste_percent": "6",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "HEA-200-S235",
        "candidate_codes": [
          "HEA-200-S235"
        ],
        "candidates": [
          {
            "code": "HEA-200-S235",
            "family": "HEA",
            "family_label": "HEA",
            "size": "200",
            "grade": "S235",
            "coating": "siyah",
            "label": "HEA 200 · S235 · siyah",
            "mass_kg_per_m": "42.30",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 24,
      "boq_no": "ANK-001",
      "description": "Zemin ankrajı — HEA 200",
      "quantity": "2.4",
      "unit": "t",
      "waste_percent": "5",
      "status": "pending",
      "match": {
        "status": "pending",
        "matched_code": null,
        "candidate_codes": [
          "HEA-200-S235"
        ],
        "candidates": [
          {
            "code": "HEA-200-S235",
            "family": "HEA",
            "family_label": "HEA",
            "size": "200",
            "grade": "S235",
            "coating": "siyah",
            "label": "HEA 200 · S235 · siyah",
            "mass_kg_per_m": "42.30",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Eksik özellik(ler): kalite, kaplama. Otomatik eşleştirme yapılmaz; kullanıcı onayı gerekir."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 25,
      "boq_no": "CEP-004",
      "description": "Cephe kuşağı — HEA 200 S235 galvaniz",
      "quantity": "120",
      "unit": "m",
      "waste_percent": "5",
      "status": "excluded",
      "match": {
        "status": "excluded",
        "matched_code": null,
        "candidate_codes": [],
        "candidates": [],
        "exclusion_reason": "catalog",
        "message": "Dört özellik eksiksiz ancak katalogda eşleşen kalem yok. Benzer ölçü/kaliteye düşürme yapılmaz."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 26,
      "boq_no": "STR-020",
      "description": "Aşı kirişi — UPN 100 S235 siyah",
      "quantity": "180",
      "unit": "m",
      "waste_percent": "6",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "UPN-100-S235",
        "candidate_codes": [
          "UPN-100-S235"
        ],
        "candidates": [
          {
            "code": "UPN-100-S235",
            "family": "UPN",
            "family_label": "UPN",
            "size": "100",
            "grade": "S235",
            "coating": "siyah",
            "label": "UPN 100 · S235 · siyah",
            "mass_kg_per_m": "10.60",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 27,
      "boq_no": "STR-021",
      "description": "Aşı kirişi — UPN 100 S235 siyah",
      "quantity": "640",
      "unit": "kg",
      "waste_percent": "6",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "UPN-100-S235",
        "candidate_codes": [
          "UPN-100-S235"
        ],
        "candidates": [
          {
            "code": "UPN-100-S235",
            "family": "UPN",
            "family_label": "UPN",
            "size": "100",
            "grade": "S235",
            "coating": "siyah",
            "label": "UPN 100 · S235 · siyah",
            "mass_kg_per_m": "10.60",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 28,
      "boq_no": "STR-022",
      "description": "Döşeme kirişi — UPN 160 S235 siyah",
      "quantity": "168",
      "unit": "m",
      "waste_percent": "5",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "UPN-160-S235",
        "candidate_codes": [
          "UPN-160-S235"
        ],
        "candidates": [
          {
            "code": "UPN-160-S235",
            "family": "UPN",
            "family_label": "UPN",
            "size": "160",
            "grade": "S235",
            "coating": "siyah",
            "label": "UPN 160 · S235 · siyah",
            "mass_kg_per_m": "18.80",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 29,
      "boq_no": "STR-023",
      "description": "Döşeme kirişi — UPN 160 S235 siyah",
      "quantity": "0.62",
      "unit": "t",
      "waste_percent": "5",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "UPN-160-S235",
        "candidate_codes": [
          "UPN-160-S235"
        ],
        "candidates": [
          {
            "code": "UPN-160-S235",
            "family": "UPN",
            "family_label": "UPN",
            "size": "160",
            "grade": "S235",
            "coating": "siyah",
            "label": "UPN 160 · S235 · siyah",
            "mass_kg_per_m": "18.80",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 30,
      "boq_no": "STR-024",
      "description": "Kritik yol — merdiven kirişi UPN 100",
      "quantity": "96",
      "unit": "m",
      "waste_percent": "5",
      "status": "pending",
      "match": {
        "status": "pending",
        "matched_code": null,
        "candidate_codes": [
          "UPN-100-S235"
        ],
        "candidates": [
          {
            "code": "UPN-100-S235",
            "family": "UPN",
            "family_label": "UPN",
            "size": "100",
            "grade": "S235",
            "coating": "siyah",
            "label": "UPN 100 · S235 · siyah",
            "mass_kg_per_m": "10.60",
            "commercial_length_m": "12"
          }
        ],
        "exclusion_reason": null,
        "message": "Eksik özellik(ler): kalite, kaplama. Otomatik eşleştirme yapılmaz; kullanıcı onayı gerekir."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 31,
      "boq_no": "MER-001",
      "description": "Korkuluk dikmesi — lama 40×5 S235 siyah",
      "quantity": "420",
      "unit": "kg",
      "waste_percent": "8",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "FLAT-40x5-S235-B",
        "candidate_codes": [
          "FLAT-40x5-S235-B"
        ],
        "candidates": [
          {
            "code": "FLAT-40x5-S235-B",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "40×5",
            "grade": "S235",
            "coating": "siyah",
            "label": "Lama 40×5 · S235 · siyah",
            "mass_kg_per_m": "1.570",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 32,
      "boq_no": "MER-002",
      "description": "Korkuluk dikmesi — lama 40×5 S235 siyah",
      "quantity": "96",
      "unit": "m",
      "waste_percent": "8",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "FLAT-40x5-S235-B",
        "candidate_codes": [
          "FLAT-40x5-S235-B"
        ],
        "candidates": [
          {
            "code": "FLAT-40x5-S235-B",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "40×5",
            "grade": "S235",
            "coating": "siyah",
            "label": "Lama 40×5 · S235 · siyah",
            "mass_kg_per_m": "1.570",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 33,
      "boq_no": "MER-003",
      "description": "Merdiven korkuluğu — lama 40×5 S235 siyah",
      "quantity": "260",
      "unit": "kg",
      "waste_percent": "8",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "FLAT-40x5-S235-B",
        "candidate_codes": [
          "FLAT-40x5-S235-B"
        ],
        "candidates": [
          {
            "code": "FLAT-40x5-S235-B",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "40×5",
            "grade": "S235",
            "coating": "siyah",
            "label": "Lama 40×5 · S235 · siyah",
            "mass_kg_per_m": "1.570",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 34,
      "boq_no": "CEP-005",
      "description": "Cephe kaplaması — lama 40×5 S235 galvaniz",
      "quantity": "150",
      "unit": "m",
      "waste_percent": "7",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "FLAT-40x5-S235-G",
        "candidate_codes": [
          "FLAT-40x5-S235-G"
        ],
        "candidates": [
          {
            "code": "FLAT-40x5-S235-G",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "40×5",
            "grade": "S235",
            "coating": "galvaniz",
            "label": "Lama 40×5 · S235 · galvaniz",
            "mass_kg_per_m": "1.570",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 35,
      "boq_no": "CEP-006",
      "description": "Cephe kaplaması — lama 40×5 S235 galvaniz",
      "quantity": "310",
      "unit": "kg",
      "waste_percent": "7",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "FLAT-40x5-S235-G",
        "candidate_codes": [
          "FLAT-40x5-S235-G"
        ],
        "candidates": [
          {
            "code": "FLAT-40x5-S235-G",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "40×5",
            "grade": "S235",
            "coating": "galvaniz",
            "label": "Lama 40×5 · S235 · galvaniz",
            "mass_kg_per_m": "1.570",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 36,
      "boq_no": "CEP-007",
      "description": "Cephe kuşağı — lama 40×5 galvaniz",
      "quantity": "180",
      "unit": "kg",
      "waste_percent": "7",
      "status": "pending",
      "match": {
        "status": "pending",
        "matched_code": null,
        "candidate_codes": [
          "FLAT-40x5-S235-G"
        ],
        "candidates": [
          {
            "code": "FLAT-40x5-S235-G",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "40×5",
            "grade": "S235",
            "coating": "galvaniz",
            "label": "Lama 40×5 · S235 · galvaniz",
            "mass_kg_per_m": "1.570",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Eksik özellik(ler): kalite. Otomatik eşleştirme yapılmaz; kullanıcı onayı gerekir."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 37,
      "boq_no": "LEV-001",
      "description": "Bağlantı levhası — lama 50×6 S235 siyah",
      "quantity": "3600",
      "unit": "kg",
      "waste_percent": "9",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "FLAT-50x6-S235-B",
        "candidate_codes": [
          "FLAT-50x6-S235-B"
        ],
        "candidates": [
          {
            "code": "FLAT-50x6-S235-B",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "50×6",
            "grade": "S235",
            "coating": "siyah",
            "label": "Lama 50×6 · S235 · siyah",
            "mass_kg_per_m": "2.355",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 38,
      "boq_no": "LEV-002",
      "description": "Bağlantı levhası — lama 50×6 S235 siyah",
      "quantity": "190",
      "unit": "m",
      "waste_percent": "9",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "FLAT-50x6-S235-B",
        "candidate_codes": [
          "FLAT-50x6-S235-B"
        ],
        "candidates": [
          {
            "code": "FLAT-50x6-S235-B",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "50×6",
            "grade": "S235",
            "coating": "siyah",
            "label": "Lama 50×6 · S235 · siyah",
            "mass_kg_per_m": "2.355",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 39,
      "boq_no": "LEV-003",
      "description": "Ankraj levhası — lama 50×6 S235 siyah",
      "quantity": "540",
      "unit": "kg",
      "waste_percent": "9",
      "status": "rule",
      "match": {
        "status": "rule",
        "matched_code": "FLAT-50x6-S235-B",
        "candidate_codes": [
          "FLAT-50x6-S235-B"
        ],
        "candidates": [
          {
            "code": "FLAT-50x6-S235-B",
            "family": "FLAT",
            "family_label": "Lama",
            "size": "50×6",
            "grade": "S235",
            "coating": "siyah",
            "label": "Lama 50×6 · S235 · siyah",
            "mass_kg_per_m": "2.355",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": null,
        "message": "Dört özellik eksiksiz ve katalogda tek kalem eşleşti."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 40,
      "boq_no": "LEV-004",
      "description": "Bağlantı levhası — kutu profil 100×100×4 S235 siyah",
      "quantity": "75",
      "unit": "m",
      "waste_percent": null,
      "status": "excluded",
      "match": {
        "status": "excluded",
        "matched_code": null,
        "candidate_codes": [
          "BOX-100-4-S235-B"
        ],
        "candidates": [
          {
            "code": "BOX-100-4-S235-B",
            "family": "BOX",
            "family_label": "Kutu profil",
            "size": "100×100×4",
            "grade": "S235",
            "coating": "siyah",
            "label": "Kutu profil 100×100×4 · S235 · siyah",
            "mass_kg_per_m": "11.70",
            "commercial_length_m": "6"
          }
        ],
        "exclusion_reason": "waste",
        "message": "Satırda fire oranı yok ve katalogda varsayılan fire tanımlı değil. Eksik fire sıfır kabul edilmez. Eşleşen kalem BOX-100-4-S235-B olsa da fire tanımsız olduğu için hesaba girmez."
      },
      "ai": null,
      "issues": [],
      "notes": []
    },
    {
      "source_row": 41,
      "boq_no": "LEV-005",
      "description": "Ankraj levhası — lama 60×6 S235 siyah",
      "quantity": "24",
      "unit": "adet",
      "waste_percent": "5",
      "status": "excluded",
      "match": {
        "status": "excluded",
        "matched_code": null,
        "candidate_codes": [],
        "candidates": [],
        "exclusion_reason": "unit",
        "message": "Birim 'adet' desteklenmiyor. Desteklenen birimler: m, kg, t."
      },
      "ai": null,
      "issues": [
        {
          "source_row": 41,
          "boq_no": "LEV-005",
          "column": "Birim",
          "code": "unit",
          "message": "Birim 'adet' bu sürümde hesap kapsamı dışında.",
          "suggestion": "Satır korunur ve 'kapsam dışı' olarak raporlanır. Hesaplamak için birimi m, kg veya t olarak girin."
        }
      ],
      "notes": []
    }
  ],
  "summary": {
    "total_rows": 40,
    "valid_rows": 40,
    "invalid_rows": 0,
    "blank_rows_skipped": 0,
    "rule": 32,
    "pending": 5,
    "excluded": 3,
    "invalid": 0
  },
  "ai": {
    "enabled": false,
    "provider": "none",
    "evaluated_rows": 0,
    "suggested": 0,
    "ambiguous": 0,
    "no_match": 0,
    "errors": 0
  },
  "warnings": [],
  "ignored_columns": [],
  "sheet_name": "Metraj"
}
