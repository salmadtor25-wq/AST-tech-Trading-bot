import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

export default function ParticleField({ count = 3000, spread = 120 }) {
  const ref = useRef()

  const { positions, sizes } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const sizes = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      // Hemisphere distribution — more in upper half
      const theta = Math.random() * Math.PI * 2
      const phi   = Math.acos(2 * Math.random() - 1)
      const r     = spread * 0.3 + Math.random() * spread * 0.7
      positions[i * 3]     = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = r * Math.cos(phi)
      sizes[i] = 0.3 + Math.random() * 0.8
    }
    return { positions, sizes }
  }, [count, spread])

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('size', new THREE.BufferAttribute(sizes, 1))
    return g
  }, [positions, sizes])

  useFrame(({ clock }) => {
    if (ref.current) {
      ref.current.rotation.y = clock.getElapsedTime() * 0.01
    }
  })

  return (
    <group ref={ref}>
      {/* Main stars */}
      <points geometry={geo}>
        <pointsMaterial
          color="#E8E0D0"
          size={0.25}
          sizeAttenuation
          transparent
          opacity={0.55}
          depthWrite={false}
        />
      </points>

      {/* Gold dust layer */}
      <GoldDust count={400} spread={spread * 0.6} />
    </group>
  )
}

function GoldDust({ count, spread }) {
  const ref = useRef()
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      arr[i * 3]     = (Math.random() - 0.5) * spread
      arr[i * 3 + 1] = (Math.random() - 0.5) * spread * 0.4
      arr[i * 3 + 2] = (Math.random() - 0.5) * spread
    }
    return arr
  }, [count, spread])

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return g
  }, [positions])

  useFrame(({ clock }) => {
    if (!ref.current) return
    ref.current.rotation.y = -clock.getElapsedTime() * 0.008
    ref.current.rotation.x = Math.sin(clock.getElapsedTime() * 0.05) * 0.05
  })

  return (
    <points ref={ref} geometry={geo}>
      <pointsMaterial
        color="#C9A227"
        size={0.18}
        sizeAttenuation
        transparent
        opacity={0.4}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}
