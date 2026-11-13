/**
 * Satır içi ikon seti.
 *
 * `lucide-react` yerine bilinçli olarak küçük, elle yazılmış SVG seti:
 * yalnızca ihtiyaç duyulan 12 ikon var, ek bağımlılık yok.
 */

type IconProps = {
  className?: string
}

const base = 'size-4 shrink-0'

function svgProps(className?: string) {
  return {
    className: className ? `${base} ${className}` : base,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.75,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
}

export function IconArrowRight({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  )
}

export function IconArrowLeft({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M19 12H5M11 18l-6-6 6-6" />
    </svg>
  )
}

export function IconCheck({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M4 12.5l5 5L20 6.5" />
    </svg>
  )
}

export function IconAlert({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M12 3.5 2.8 20h18.4L12 3.5Z" />
      <path d="M12 9.5v4.5M12 17.2v.3" />
    </svg>
  )
}

export function IconClose({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  )
}

export function IconSearch({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M15.5 15.5 21 21" />
    </svg>
  )
}

export function IconUpload({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16" />
    </svg>
  )
}

export function IconFile({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M13.5 3H7a1.5 1.5 0 0 0-1.5 1.5v15A1.5 1.5 0 0 0 7 21h10a1.5 1.5 0 0 0 1.5-1.5V8L13.5 3Z" />
      <path d="M13 3v5.5h5.5" />
    </svg>
  )
}

export function IconChevronDown({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M6 9.5l6 6 6-6" />
    </svg>
  )
}

export function IconChevronRight({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M9 6l6 6-6 6" />
    </svg>
  )
}

export function IconInfo({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5.5M12 7.8v.3" />
    </svg>
  )
}

export function IconLock({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <rect x="4.5" y="10.5" width="15" height="9.5" rx="1.5" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    </svg>
  )
}

export function IconLayers({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M12 3.5 3.5 8l8.5 4.5L20.5 8 12 3.5Z" />
      <path d="M3.5 13l8.5 4.5 8.5-4.5" />
    </svg>
  )
}
