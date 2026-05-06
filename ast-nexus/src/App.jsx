import { useState, useEffect, useRef, useCallback } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'
import 'lenis/dist/lenis.css'
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

const CAM_PHASES = [
  { x: 0,   y: 18,  z: 55,  lx: 0, ly: 0,  lz: 0  },
  { x: 10,  y: 10,  z: 35,  lx: 0, ly: 1,  lz: 0  },
  { x: -14, y: 5,   z: 28,  lx: 0, ly: 2,  lz: 0  },
  { x: 6,   y: -3,  z: 22,  lx: 0, ly: 0,  lz: 0  },
  { x: 0,   y: 22,  z: 50,  lx: 0, ly: -2, lz: 0  },
]

const SECTION_RANGES = [
  [0.00, 0.18],
  [0.16, 0.36],
  [0.34, 0.56],
  [0.54, 0.76],
  [0.78, 1.00],
]

export default function App() {
  const [loaded, setLoaded]               = useState(false)
  const [activeSection, setActiveSection] = useState(0)
  const [scrollProgress, setScrollProgress] = useState(0)
  const [showPanels, setShowPanels]       = useState(false)
  const [showHint, setShowHint]           = useState(true)

  const camProxy = useRef({ ...CAM_PHASES[0] })

  const handleLoaded = useCallback(() => setLoaded(true), [])

  useEffect(() => {
    if (!loaded) return

    // ── Lenis smooth scroll ──────────────────────────────────────
    const lenis = new Lenis({ lerp: 0.07, smoothWheel: true })

    // Keep ScrollTrigger in sync with Lenis scroll position
    const onLenisScroll = () => ScrollTrigger.update()
    lenis.on('scroll', onLenisScroll)

    // Drive Lenis via GSAP ticker (store ref for cleanup)
    const lenisRaf = time => lenis.raf(time * 1000)
    gsap.ticker.add(lenisRaf)
    gsap.ticker.lagSmoothing(0)

    // ── ScrollTrigger timeline ───────────────────────────────────
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

          let active = 0
          SECTION_RANGES.forEach(([start, end], i) => {
            if (p >= start && p <= end) active = i
          })
          setActiveSection(active)
          setShowPanels(p >= 0.34 && p <= 0.56)
        },
      },
    })

    const dur = 25
    CAM_PHASES.forEach((phase, i) => {
      tl.to(camProxy.current, {
        x: phase.x, y: phase.y, z: phase.z,
        lx: phase.lx, ly: phase.ly, lz: phase.lz,
        duration: dur,
        ease: 'power2.inOut',
      }, i === 0 ? 0 : `>-${dur * 0.35}`)
    })

    return () => {
      // Full cleanup — critical for React StrictMode double-mount
      lenis.off('scroll', onLenisScroll)
      gsap.ticker.remove(lenisRaf)
      lenis.destroy()
      ScrollTrigger.getAll().forEach(t => t.kill())
      tl.kill()
    }
  }, [loaded])

  return (
    <>
      {!loaded && <Loader onComplete={handleLoaded} />}

      <div className="scanlines" />

      <Scene
        camProxy={camProxy}
        scrollProgress={scrollProgress}
        showPanels={showPanels}
      />

      {loaded && (
        <HUD
          activeSection={activeSection}
          scrollProgress={scrollProgress}
          showHint={showHint}
        />
      )}

      {loaded && (
        <div className="sections">
          <HeroSection      active={activeSection === 0} />
          <NexusCoreSection active={activeSection === 1} />
          <AISystemsSection active={activeSection === 2} />
          <InfraSection     active={activeSection === 3} />
          <CTASection       active={activeSection === 4} />
        </div>
      )}

      <div id="scroll-space" />
    </>
  )
}
