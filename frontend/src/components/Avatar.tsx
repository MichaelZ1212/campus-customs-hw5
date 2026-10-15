import { identity } from '../agents'

export function Avatar({ name, size = 28, pulse = false }: { name: string; size?: number; pulse?: boolean }) {
  const id = identity(name)
  return (
    <span
      className={`avatar${pulse ? ' avatar--pulse' : ''}`}
      style={{ '--c': id.color, width: size, height: size } as React.CSSProperties}
      title={`${id.label} - ${id.role}`}
    >
      {id.icon}
    </span>
  )
}
