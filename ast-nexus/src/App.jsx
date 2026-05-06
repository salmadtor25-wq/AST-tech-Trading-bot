import { useState, useEffect, useRef, useCallback } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'
import Scene from './components/Scene'
import Loader from './components/Loader'
import HUD from './components/hud/HUD'
import {
  HeroSection,
  NexusCoreSection,
  AISystemsSection,
  InfraSection,
  CTASection,
} from './components/sections/Sections'

gsap.registerPlugin(ScrollTrigger)

// Camera positions per section
const CAM_PHASES = [
  // Hero — wide, chip floating from afar
  { x: 0,   y: 18,  z: 55,  lx: 0, ly: 0,  lz: 0  },
  // Nexus Core — pull in, slight above
  { x: 10,  y: 10,  z: 35,  lx: 0, ly: 1,  lz: 0  },
  // AI Systems — side angle, medium close
  { x: -14, y: 5,   z: 28,  lx: 0, ly: 2,  lz: 0  },
  // Infrastructure — from below / dramatic
  { x: 6,   y: -3,  z: 22,  lx: 0, ly: 0,  lz: 0  },
  // CTA — pulled back, elevated
  { x: 0,   y: 22,  z: 50,  lx: 0, ly: -2, lz: 0  },
]

// Scroll ranges [0..1] where each section is "active"
const SECTION_RANGES = [
  [0.00, 0.18],
  [0.16, 0.36],
  [0.34, 0.56],
  [0.54, 0.76],
  [0.78, 1.00],
]

export default function App() {
  const [loaded, setLoaded] = useState(false)
  const [activeSection, setActiveSection] = useState(0)
  const [scrollProgress, setScrollProgress] = useState(0)
  const [showPanels, setShowPanels] = useState(false)
  const [showHint, setShowHint]   = useState(true)

  // Camera proxy (mutated by GSAP, read by Three.js each frame)
  const camProxy = useRef({ ...CAM_PHASES[0] })
  const lenisRef = useRef(null)

  const handleLoaded = useCallback(() => {
    setLoaded(true)
    setShowPanels(true)
  }, [])

  // Smooth scroll + GSAP ScrollTrigger setup
  useEffect(() => {
    if (!loaded) return

    // Lenis smooth scroll
    const lenis = new Lenis({ lerp: 0.07, smoothWheel: true })
    lenisRef.current = lenis

    lenis.on('scroll', ScrollTrigger.update)
    gsap.ticker.add(time => lenis.raf(time * 1000))
    gsap.ticker.lagSmoothing(0)

    // Main scroll timeline
    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: '#scroll-space',
        start: 'top top',
        end: 'bottom bottom',
        scrub: 2.0,
        onUpdate: self => {
          const p = self.progress
          setScrollProgress(p)
          setShowHint(p < 0.05)

          // Determine active section
          let active = 0
          SECTION_RANGES.forEach(([start, end], i) => {
            if (p >= start && p <= end) active = i
          })
          setActiveSection(active)

          // AI Systems section toggles holographic panels
          setShowPanels(p >= 0.34 && p <= 0.56)
        },
      },
    })

    // Animate camera proxy through phases
    const dur = 25 // duration units per phase
    CAM_PHASES.forEach((phase, i) => {
      tl.to(camProxy.current, {
        x: phase.x, y: phase.y, z: phase.z,
        lx: phase.lx, ly: phase.ly, lz: phase.lz,
        duration: dur,
        ease: 'power2.inOut',
      }, i === 0 ? 0 : `>-${dur * 0.35}`)
    })

    return () => {
      lenis.destroy()
      ScrollTrigger.getAll().forEach(t => t.kill())
      tl.kill()
    }
  }, [loaded])

  return (
    <>
      {/* Loading screen */}
      {!loaded && <Loader onComplete={handleLoaded} />}

      {/* Scanlines */}
      <div className="scanlines" />

      {/* 3D WebGL canvas (fixed) */}
      <Scene
        camProxy={camProxy}
        scrollProgress={scrollProgress}
        showPanels={showPanels}
      />

      {/* HUD overlay */}
      {loaded && (
        <HUD
          activeSection={activeSection}
          scrollProgress={scrollProgress}
          showHint={showHint}
        />
      )}

      {/* HTML text sections (fixed, fade in/out) */}
      {loaded && (
        <div className="sections">
          <HeroSection    active={activeSection === 0} />
          <NexusCoreSection active={activeSection === 1} />
          <AISystemsSection active={activeSection === 2} />
          <InfraSection   active={activeSection === 3} />
          <CTASection     active={activeSection === 4} />
        </div>
      )}

      {/* Scroll spacer — drives ScrollTrigger */}
      <div id="scroll-space" />
    </>
  )
}
