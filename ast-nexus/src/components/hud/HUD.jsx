import { useEffect, useRef } from 'react'

const SECTIONS = ['Hero', 'Nexus Core', 'AI Systems', 'Infrastructure', 'Enter Nexus']

export default function HUD({ activeSection, scrollProgress, showHint }) {
  const scrollTo = idx => {
    const total = document.documentElement.scrollHeight - window.innerHeight
    window.scrollTo({ top: (idx / (SECTIONS.length - 1)) * total, behavior: 'smooth' })
  }

  return (
    <div className="hud">
      {/* Progress bar */}
      <div className="hud-progress" style={{ width: `${scrollProgress * 100}%` }} />

      {/* Top bar */}
      <div className="hud-top">
        <div className="hud-logo">
          AST Nexus
          <span>Digital Intelligence</span>
        </div>
        <nav className="hud-nav">
          <a onClick={() => scrollTo(0)}>Systems</a>
          <a onClick={() => scrollTo(1)}>Core</a>
          <a onClick={() => scrollTo(2)}>AI</a>
          <a onClick={() => scrollTo(3)}>Infrastructure</a>
          <a className="nav-cta" onClick={() => scrollTo(4)}>Enter Nexus</a>
        </nav>
      </div>

      {/* Side dots */}
      <div className="hud-dots">
        {SECTIONS.map((s, i) => (
          <button
            key={i}
            className={`hud-dot ${activeSection === i ? 'active' : ''}`}
            onClick={() => scrollTo(i)}
            title={s}
          />
        ))}
      </div>

      {/* Scroll hint */}
      <div className="scroll-hint" style={{ opacity: showHint ? 1 : 0 }}>
        <span>Scroll</span>
        <div className="scroll-hint-line" />
      </div>

      {/* Corner marks */}
      <div className="corner-mark cm-tl" />
      <div className="corner-mark cm-tr" />
      <div className="corner-mark cm-bl" />
      <div className="corner-mark cm-br" />
    </div>
  )
}
