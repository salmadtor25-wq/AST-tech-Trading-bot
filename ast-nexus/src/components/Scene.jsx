import { useRef, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'
import * as THREE from 'three'
import NexusChip from './chip/NexusChip'
import DataStreams from './chip/DataStreams'
import AINodes from './chip/AINodes'
import ParticleField from './particles/ParticleField'
import NetworkGrid from './chip/NetworkGrid'

// Camera rig — reads from proxy object
function CameraRig({ camProxy, mouseRef }) {
  const { camera } = useThree()

  useFrame(() => {
    // Smoothly interpolate camera position toward proxy target
    camera.position.x += (camProxy.current.x + mouseRef.current.x - camera.position.x) * 0.04
    camera.position.y += (camProxy.current.y + mouseRef.current.y - camera.position.y) * 0.04
    camera.position.z += (camProxy.current.z - camera.position.z) * 0.04

    const targetLook = new THREE.Vector3(
      camProxy.current.lx,
      camProxy.current.ly,
      camProxy.current.lz
    )
    camera.lookAt(targetLook)
  })
  return null
}

// Nebula sky dome
function NebulaSky() {
  const meshRef = useRef()
  useFrame(({ clock }) => {
    if (meshRef.current) meshRef.current.rotation.y = clock.getElapsedTime() * 0.004
  })
  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[200, 32, 32]} />
      <meshBasicMaterial color="#04030A" side={THREE.BackSide} />
    </mesh>
  )
}

// Subtle ground plane / reflection
function GroundPlane() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -8, 0]}>
      <planeGeometry args={[200, 200, 1, 1]} />
      <meshStandardMaterial color="#04030A" metalness={0.9} roughness={0.8} transparent opacity={0.5} />
    </mesh>
  )
}

// Floating holographic panels (AI Systems section)
function HoloPanels({ visible }) {
  const panelData = [
    { pos: [-8, 2, -3], title: 'PREDICTIVE AI', col: '#C9A227' },
    { pos: [ 8, 3, -3], title: 'AUTOMATION',   col: '#4D7FFF' },
    { pos: [-6,-1,  4], title: 'ANALYTICS',    col: '#C9A227' },
    { pos: [ 7,-2,  4], title: 'DASHBOARDS',   col: '#00D4FF' },
  ]

  const refs = useRef([])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    refs.current.forEach((g, i) => {
      if (!g) return
      g.position.y = panelData[i].pos[1] + Math.sin(t * 0.5 + i) * 0.3
      g.rotation.y = Math.sin(t * 0.2 + i) * 0.12
    })
  })

  if (!visible) return null

  return (
    <group>
      {panelData.map((p, i) => (
        <group key={i} position={p.pos} ref={el => refs.current[i] = el}>
          {/* Panel frame */}
          <mesh>
            <boxGeometry args={[2.8, 1.8, 0.04]} />
            <meshStandardMaterial color="#0A0820" transparent opacity={0.7} metalness={0.9} roughness={0.1} emissive={p.col} emissiveIntensity={0.05} />
          </mesh>
          {/* Border glow */}
          {[[-1.4,0,0],[1.4,0,0],[0,-0.9,0],[0,0.9,0]].map((off, j) => (
            <mesh key={j} position={off}>
              <boxGeometry args={[
                j < 2 ? 0.02 : 2.8,
                j < 2 ? 1.8 : 0.02,
                0.05
              ]} />
              <meshBasicMaterial color={p.col} transparent opacity={0.5} />
            </mesh>
          ))}
          {/* Corner accents */}
          {[[-1.3, 0.8],[1.3, 0.8],[-1.3,-0.8],[1.3,-0.8]].map(([cx,cy],j) => (
            <mesh key={`c${j}`} position={[cx, cy, 0.03]}>
              <sphereGeometry args={[0.05, 6, 6]} />
              <meshStandardMaterial color={p.col} emissive={p.col} emissiveIntensity={1} />
            </mesh>
          ))}
        </group>
      ))}
    </group>
  )
}

// Ambient point lights
function SceneLights() {
  const goldRef  = useRef()
  const blueRef  = useRef()
  const cyanRef  = useRef()

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (goldRef.current) goldRef.current.intensity = 1.5 + Math.sin(t * 0.7) * 0.3
    if (blueRef.current) blueRef.current.intensity = 1.2 + Math.sin(t * 0.5 + 1) * 0.25
    if (cyanRef.current) cyanRef.current.intensity = 0.8 + Math.sin(t * 0.9 + 2) * 0.2
  })

  return (
    <>
      <ambientLight intensity={0.15} color="#1A1020" />
      <pointLight ref={goldRef} position={[12, 8, 6]}  color="#C9A227" intensity={1.5} distance={60} decay={2} castShadow />
      <pointLight ref={blueRef} position={[-10, 6, -8]} color="#1A3AFF" intensity={1.2} distance={55} decay={2} />
      <pointLight ref={cyanRef} position={[0, -12, 10]} color="#00D4FF" intensity={0.8} distance={45} decay={2} />
      <pointLight position={[0, 20, 0]} color="#A0712A" intensity={0.6} distance={40} decay={2} />
      <directionalLight position={[5, 15, 5]} intensity={0.5} color="#C9A227" castShadow />
    </>
  )
}

export default function Scene({ camProxy, scrollProgress, showPanels }) {
  const mouseRef = useRef({ x: 0, y: 0 })

  useEffect(() => {
    const onMove = e => {
      mouseRef.current.x = ((e.clientX / window.innerWidth) - 0.5) * 3
      mouseRef.current.y = -((e.clientY / window.innerHeight) - 0.5) * 1.5
    }
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  return (
    <Canvas
      id="nexus-canvas"
      camera={{ position: [0, 18, 55], fov: 52, near: 0.1, far: 500 }}
      dpr={[1, 2]}
      shadows
      gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.0 }}
    >
      <CameraRig camProxy={camProxy} mouseRef={mouseRef} />
      <NebulaSky />
      <SceneLights />
      <ParticleField count={2800} spread={100} />
      <NetworkGrid />
      <group position={[0, 0, 0]}>
        <NexusChip scrollProgress={scrollProgress} />
        <DataStreams />
        <AINodes />
      </group>
      <HoloPanels visible={showPanels} />
      <GroundPlane />
      <fog attach="fog" args={['#04030A', 40, 180]} />
      <EffectComposer>
        <Bloom
          intensity={1.2}
          luminanceThreshold={0.2}
          luminanceSmoothing={0.9}
          blendFunction={BlendFunction.ADD}
          mipmapBlur
        />
        <Vignette eskil={false} offset={0.35} darkness={0.8} />
      </EffectComposer>
    </Canvas>
  )
}
