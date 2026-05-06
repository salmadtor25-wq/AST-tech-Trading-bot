import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

function Stream({ start, end, color, speed, delay }) {
  const ref = useRef()
  const count = 60
  const positions = useMemo(() => new Float32Array(count * 3), [])
  const opacities = useMemo(() => {
    const a = new Float32Array(count)
    for (let i = 0; i < count; i++) a[i] = i / count
    return a
  }, [])

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('opacity', new THREE.BufferAttribute(opacities, 1))
    return g
  }, [positions, opacities])

  useFrame(({ clock }) => {
    const t = (clock.getElapsedTime() * speed + delay) % 1
    const dir = new THREE.Vector3().subVectors(end, start)
    const pos = geo.attributes.position
    for (let i = 0; i < count; i++) {
      const frac = ((t + (i / count) * 0.4) % 1)
      const p = new THREE.Vector3().copy(start).addScaledVector(dir, frac)
      pos.setXYZ(i, p.x, p.y, p.z)
    }
    pos.needsUpdate = true
  })

  return (
    <points geometry={geo}>
      <pointsMaterial
        color={color}
        size={0.06}
        transparent
        opacity={0.7}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        sizeAttenuation
      />
    </points>
  )
}

export default function DataStreams() {
  const streams = useMemo(() => {
    const arr = []
    const colors = ['#C9A227', '#E8C547', '#00D4FF', '#4D7FFF', '#A0712A']
    for (let i = 0; i < 16; i++) {
      const angle = (i / 16) * Math.PI * 2
      const r1 = 6 + Math.random() * 2
      const r2 = 14 + Math.random() * 6
      arr.push({
        start: new THREE.Vector3(
          Math.cos(angle) * r1, (Math.random() - 0.5) * 1,
          Math.sin(angle) * r1
        ),
        end: new THREE.Vector3(
          Math.cos(angle + 0.4) * r2,
          (Math.random() - 0.5) * 6,
          Math.sin(angle + 0.4) * r2
        ),
        color: colors[i % colors.length],
        speed: 0.18 + Math.random() * 0.2,
        delay: Math.random(),
      })
    }
    return arr
  }, [])

  return (
    <group>
      {streams.map((s, i) => (
        <Stream key={i} {...s} />
      ))}
    </group>
  )
}
