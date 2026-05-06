import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

function NodeConnection({ a, b }) {
  const points = useMemo(() => [a, b], [a, b])
  const geo = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points])
  return (
    <line geometry={geo}>
      <lineBasicMaterial color="#C9A227" transparent opacity={0.12} />
    </line>
  )
}

function AINode({ position, radius, phase, speed }) {
  const meshRef = useRef()
  const ringRef = useRef()

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (meshRef.current) {
      meshRef.current.material.emissiveIntensity = 0.5 + Math.sin(t * speed + phase) * 0.35
    }
    if (ringRef.current) {
      ringRef.current.rotation.z = t * speed * 0.5
      ringRef.current.rotation.x = t * speed * 0.3
    }
  })

  return (
    <group position={position}>
      {/* Core sphere */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[radius, 12, 12]} />
        <meshStandardMaterial
          color="#0A0820"
          emissive="#4D7FFF"
          emissiveIntensity={0.6}
          metalness={0.9}
          roughness={0.1}
          transparent
          opacity={0.85}
        />
      </mesh>
      {/* Outer glow sphere */}
      <mesh>
        <sphereGeometry args={[radius * 1.6, 8, 8]} />
        <meshBasicMaterial color="#4D7FFF" transparent opacity={0.04} depthWrite={false} />
      </mesh>
      {/* Orbital ring */}
      <group ref={ringRef}>
        <mesh>
          <torusGeometry args={[radius * 2, 0.015, 4, 40]} />
          <meshBasicMaterial color="#C9A227" transparent opacity={0.35} />
        </mesh>
      </group>
      {/* Gold dot */}
      <mesh position={[0, radius * 1.1, 0]}>
        <sphereGeometry args={[0.04, 6, 6]} />
        <meshStandardMaterial color="#C9A227" emissive="#E8C547" emissiveIntensity={1} />
      </mesh>
    </group>
  )
}

export default function AINodes() {
  const nodes = useMemo(() => {
    const arr = []
    const positions = [
      new THREE.Vector3( 8,  2, -4),
      new THREE.Vector3(-7,  1,  5),
      new THREE.Vector3( 3,  4,  8),
      new THREE.Vector3(-9,  3, -6),
      new THREE.Vector3( 6, -2,  7),
      new THREE.Vector3(-4,  5, -9),
      new THREE.Vector3(10,  1,  3),
      new THREE.Vector3(-6, -1,  2),
    ]
    positions.forEach((p, i) => {
      arr.push({
        position: p,
        radius: 0.25 + Math.random() * 0.2,
        phase: (i / positions.length) * Math.PI * 2,
        speed: 0.6 + Math.random() * 0.5,
      })
    })
    return arr
  }, [])

  // Connection pairs (indices)
  const connections = useMemo(() => [
    [0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[0,4],[2,6],[1,5]
  ], [])

  return (
    <group>
      {nodes.map((n, i) => (
        <AINode key={i} {...n} />
      ))}
      {connections.map(([a, b], i) => (
        <NodeConnection key={i} a={nodes[a].position} b={nodes[b].position} />
      ))}
    </group>
  )
}
