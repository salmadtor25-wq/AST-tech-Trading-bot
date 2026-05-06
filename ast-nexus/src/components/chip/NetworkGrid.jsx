import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// Floating hexagonal network nodes connecting the environment
function HexNode({ position, size = 0.3 }) {
  const ref = useRef()
  const phase = useMemo(() => Math.random() * Math.PI * 2, [])
  useFrame(({ clock }) => {
    if (!ref.current) return
    ref.current.material.opacity = 0.15 + Math.sin(clock.getElapsedTime() * 0.8 + phase) * 0.1
  })
  return (
    <mesh ref={ref} position={position}>
      <octahedronGeometry args={[size, 0]} />
      <meshBasicMaterial color="#1A3AFF" transparent opacity={0.2} wireframe />
    </mesh>
  )
}

export default function NetworkGrid() {
  const nodes = useMemo(() => {
    const arr = []
    for (let i = 0; i < 20; i++) {
      const angle = (i / 20) * Math.PI * 2 + Math.random() * 0.5
      const r = 18 + Math.random() * 14
      arr.push(new THREE.Vector3(
        Math.cos(angle) * r,
        (Math.random() - 0.5) * 16,
        Math.sin(angle) * r
      ))
    }
    return arr
  }, [])

  const lineGeo = useMemo(() => {
    const pairs = []
    nodes.forEach((n, i) => {
      // Connect to nearby nodes
      nodes.forEach((m, j) => {
        if (i >= j) return
        if (n.distanceTo(m) < 16) {
          pairs.push(n, m)
        }
      })
    })
    return new THREE.BufferGeometry().setFromPoints(pairs)
  }, [nodes])

  const ringRef = useRef()
  useFrame(({ clock }) => {
    if (ringRef.current) ringRef.current.rotation.y = clock.getElapsedTime() * 0.015
  })

  return (
    <group ref={ringRef}>
      {nodes.map((pos, i) => (
        <HexNode key={i} position={pos} size={0.2 + Math.random() * 0.3} />
      ))}
      <lineSegments geometry={lineGeo}>
        <lineBasicMaterial color="#1A3AFF" transparent opacity={0.06} />
      </lineSegments>

      {/* Two large rotating rings in background */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[28, 0.04, 4, 120]} />
        <meshBasicMaterial color="#C9A227" transparent opacity={0.08} />
      </mesh>
      <mesh rotation={[Math.PI / 3, 0, 0.6]}>
        <torusGeometry args={[38, 0.03, 4, 120]} />
        <meshBasicMaterial color="#4D7FFF" transparent opacity={0.06} />
      </mesh>
    </group>
  )
}
