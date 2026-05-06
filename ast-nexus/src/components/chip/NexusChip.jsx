import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// Procedural circuit line geometry on chip surface
function CircuitTraces({ size = 5 }) {
  const geo = useMemo(() => {
    const points = []
    const segs = 18
    const step = (size * 2) / segs

    // Horizontal traces
    for (let r = 0; r < 6; r++) {
      const y = -size + step * (2 + r * 2.4)
      const x0 = -size + step * (Math.random() * 2)
      const x1 = size - step * (Math.random() * 2)
      points.push(new THREE.Vector3(x0, 0.26, y))
      points.push(new THREE.Vector3(x1, 0.26, y))
    }
    // Vertical traces
    for (let c = 0; c < 6; c++) {
      const x = -size + step * (2 + c * 2.4)
      const z0 = -size + step * (Math.random() * 2)
      const z1 = size - step * (Math.random() * 2)
      points.push(new THREE.Vector3(x, 0.26, z0))
      points.push(new THREE.Vector3(x, 0.26, z1))
    }
    // L-shaped connectors
    for (let i = 0; i < 8; i++) {
      const sx = (Math.random() - 0.5) * size * 1.6
      const sz = (Math.random() - 0.5) * size * 1.6
      const ex = sx + (Math.random() - 0.5) * size * 0.8
      const ez = sz + (Math.random() - 0.5) * size * 0.8
      // Corner turn
      points.push(new THREE.Vector3(sx, 0.26, sz))
      points.push(new THREE.Vector3(ex, 0.26, sz))
      points.push(new THREE.Vector3(ex, 0.26, sz))
      points.push(new THREE.Vector3(ex, 0.26, ez))
    }

    const buf = new THREE.BufferGeometry()
    buf.setFromPoints(points)
    return buf
  }, [size])

  return (
    <lineSegments geometry={geo}>
      <lineBasicMaterial color="#C9A227" transparent opacity={0.6} />
    </lineSegments>
  )
}

// Solder pads around chip edges
function EdgePads({ size = 5 }) {
  const pads = useMemo(() => {
    const arr = []
    const count = 10
    const sides = ['top', 'bottom', 'left', 'right']
    sides.forEach(side => {
      for (let i = 0; i < count; i++) {
        const t = -size + (i / (count - 1)) * size * 2
        let x = 0, z = 0
        if (side === 'top')    { x = t; z = -size - 0.1 }
        if (side === 'bottom') { x = t; z =  size + 0.1 }
        if (side === 'left')   { x = -size - 0.1; z = t }
        if (side === 'right')  { x =  size + 0.1; z = t }
        arr.push({ x, z })
      }
    })
    return arr
  }, [size])

  return (
    <group>
      {pads.map((p, i) => (
        <mesh key={i} position={[p.x, 0.27, p.z]}>
          <boxGeometry args={[0.18, 0.06, 0.45]} />
          <meshStandardMaterial color="#A0712A" metalness={0.95} roughness={0.1} emissive="#C9A227" emissiveIntensity={0.2} />
        </mesh>
      ))}
    </group>
  )
}

// Glowing AI nodes on chip surface (small spheres)
function AISurface({ size = 5 }) {
  const nodes = useMemo(() => {
    const arr = []
    for (let i = 0; i < 14; i++) {
      arr.push({
        x: (Math.random() - 0.5) * size * 1.6,
        z: (Math.random() - 0.5) * size * 1.6,
        s: 0.08 + Math.random() * 0.12,
        phase: Math.random() * Math.PI * 2,
      })
    }
    return arr
  }, [size])

  const refs = useRef([])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    refs.current.forEach((m, i) => {
      if (!m) return
      const n = nodes[i]
      m.material.emissiveIntensity = 0.4 + Math.sin(t * 1.5 + n.phase) * 0.3
    })
  })

  return (
    <group>
      {nodes.map((n, i) => (
        <mesh key={i} position={[n.x, 0.35, n.z]} ref={el => refs.current[i] = el}>
          <sphereGeometry args={[n.s, 8, 8]} />
          <meshStandardMaterial color="#C9A227" emissive="#E8C547" emissiveIntensity={0.5} roughness={0.1} metalness={0.8} />
        </mesh>
      ))}
    </group>
  )
}

// Central die (processor core)
function CentralDie() {
  const ref = useRef()
  useFrame(({ clock }) => {
    if (!ref.current) return
    ref.current.material.emissiveIntensity = 0.3 + Math.sin(clock.getElapsedTime() * 0.8) * 0.15
  })
  return (
    <group>
      {/* Core body */}
      <mesh ref={ref} position={[0, 0.32, 0]}>
        <boxGeometry args={[3.5, 0.08, 3.5]} />
        <meshStandardMaterial color="#0A0820" emissive="#1A3AFF" emissiveIntensity={0.3} metalness={0.9} roughness={0.15} />
      </mesh>
      {/* Grid lines on die */}
      {[-1.2, -0.4, 0.4, 1.2].map((v, i) => (
        <group key={i}>
          <mesh position={[v, 0.37, 0]}>
            <boxGeometry args={[0.02, 0.01, 3.5]} />
            <meshStandardMaterial color="#4D7FFF" emissive="#4D7FFF" emissiveIntensity={0.8} />
          </mesh>
          <mesh position={[0, 0.37, v]}>
            <boxGeometry args={[3.5, 0.01, 0.02]} />
            <meshStandardMaterial color="#4D7FFF" emissive="#4D7FFF" emissiveIntensity={0.8} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

export default function NexusChip({ scrollProgress = 0 }) {
  const groupRef = useRef()
  const chipSize = 5.5

  useFrame(({ clock }) => {
    if (!groupRef.current) return
    const t = clock.getElapsedTime()
    groupRef.current.rotation.y = t * 0.06
    // Subtle float
    groupRef.current.position.y = Math.sin(t * 0.35) * 0.18
  })

  return (
    <group ref={groupRef}>
      {/* Main chip substrate */}
      <mesh position={[0, 0, 0]} receiveShadow castShadow>
        <boxGeometry args={[chipSize * 2, 0.5, chipSize * 2]} />
        <meshStandardMaterial
          color="#0D0B18"
          metalness={0.85}
          roughness={0.2}
          envMapIntensity={1}
        />
      </mesh>

      {/* Top surface (darker silicon) */}
      <mesh position={[0, 0.26, 0]}>
        <boxGeometry args={[chipSize * 1.95, 0.02, chipSize * 1.95]} />
        <meshStandardMaterial color="#080618" metalness={0.9} roughness={0.1} />
      </mesh>

      {/* Gold perimeter frame */}
      {[
        [chipSize * 1.95, 0.02, 0.08, 0, 0.28, 0],
        [0.08, 0.02, chipSize * 1.95, 0, 0.28, 0],
      ].map(([w, h, d, x, y, z], i) => (
        <group key={i}>
          <mesh position={[x + (i === 0 ? 0 : chipSize * 0.97), y, z]}>
            <boxGeometry args={[w, h, d]} />
            <meshStandardMaterial color="#A0712A" metalness={0.95} roughness={0.05} emissive="#C9A227" emissiveIntensity={0.15} />
          </mesh>
          <mesh position={[x - (i === 0 ? 0 : chipSize * 0.97), y, z]}>
            <boxGeometry args={[w, h, d]} />
            <meshStandardMaterial color="#A0712A" metalness={0.95} roughness={0.05} emissive="#C9A227" emissiveIntensity={0.15} />
          </mesh>
          <mesh position={[x, y, z + (i === 1 ? 0 : chipSize * 0.97)]}>
            <boxGeometry args={[w, h, d]} />
            <meshStandardMaterial color="#A0712A" metalness={0.95} roughness={0.05} emissive="#C9A227" emissiveIntensity={0.15} />
          </mesh>
          <mesh position={[x, y, z - (i === 1 ? 0 : chipSize * 0.97)]}>
            <boxGeometry args={[w, h, d]} />
            <meshStandardMaterial color="#A0712A" metalness={0.95} roughness={0.05} emissive="#C9A227" emissiveIntensity={0.15} />
          </mesh>
        </group>
      ))}

      {/* Circuit traces on surface */}
      <CircuitTraces size={chipSize * 0.9} />

      {/* Edge solder pads */}
      <EdgePads size={chipSize} />

      {/* Central die */}
      <CentralDie />

      {/* AI nodes */}
      <AISurface size={chipSize * 0.85} />

      {/* Underside bump array */}
      <BumpArray size={chipSize} />
    </group>
  )
}

function BumpArray({ size }) {
  const bumps = useMemo(() => {
    const arr = []
    const cols = 9, rows = 9
    const spacing = (size * 1.8) / cols
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        arr.push({
          x: -size * 0.9 + c * spacing + spacing * 0.5,
          z: -size * 0.9 + r * spacing + spacing * 0.5,
        })
      }
    }
    return arr
  }, [size])

  return (
    <group>
      {bumps.map((b, i) => (
        <mesh key={i} position={[b.x, -0.28, b.z]}>
          <sphereGeometry args={[0.08, 6, 6]} />
          <meshStandardMaterial color="#C9A227" metalness={0.9} roughness={0.2} />
        </mesh>
      ))}
    </group>
  )
}
