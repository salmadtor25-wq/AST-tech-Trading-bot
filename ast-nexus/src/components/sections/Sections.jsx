import { motion, AnimatePresence } from 'framer-motion'

const fade = {
  hidden:  { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] } },
  exit:    { opacity: 0, y: -16, transition: { duration: 0.4 } },
}

function Panel({ children, active, className = '' }) {
  return (
    <div className={`section-panel ${active ? 'active' : ''} ${className}`}>
      <AnimatePresence>
        {active && (
          <motion.div
            key="content"
            variants={fade}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function HeroSection({ active }) {
  return (
    <Panel active={active}>
      <div className="hero-content">
        <div className="hero-eyebrow">Est. 2024 — Next Generation Systems</div>
        <h1 className="hero-title">
          AST <em>Nexus</em>
        </h1>
        <p className="hero-subtitle">
          Intelligence. &nbsp;Automation. &nbsp;Digital Infrastructure.
        </p>
      </div>
    </Panel>
  )
}

export function NexusCoreSection({ active }) {
  return (
    <Panel active={active}>
      <div className="panel-inner right">
        <div className="panel-eyebrow">Section 02 — Nexus Core</div>
        <h2 className="panel-title">
          One <em>Intelligent</em><br />Ecosystem
        </h2>
        <p className="panel-body">
          AST Nexus connects AI systems, automation engines, and software
          infrastructure into a single unified digital intelligence platform.
          Every node communicates. Every signal is processed. Nothing is wasted.
        </p>
        <div className="metrics-row">
          <div>
            <div className="metric-val">99.9%</div>
            <div className="metric-label">Uptime</div>
          </div>
          <div>
            <div className="metric-val">&lt;1ms</div>
            <div className="metric-label">Latency</div>
          </div>
          <div>
            <div className="metric-val">∞</div>
            <div className="metric-label">Scale</div>
          </div>
        </div>
      </div>
    </Panel>
  )
}

export function AISystemsSection({ active }) {
  const cards = [
    { icon: '◈', title: 'Predictive Intelligence', body: 'Neural pattern recognition with real-time market forecasting.' },
    { icon: '⚙', title: 'Automation Engines', body: 'Workflow automation across distributed infrastructure layers.' },
    { icon: '▲', title: 'Trading Analytics', body: 'Sub-millisecond signal analysis with 8-layer confirmation logic.' },
    { icon: '◉', title: 'Smart Dashboards', body: 'Live telemetry across all connected systems in one unified view.' },
  ]

  return (
    <Panel active={active}>
      <div className="panel-inner left">
        <div className="panel-eyebrow">Section 03 — AI Systems</div>
        <h2 className="panel-title">
          Machine<br /><em>Intelligence</em>
        </h2>
        <p className="panel-body">
          Four core intelligence modules operating in concert — sensing,
          deciding, executing, and adapting in real time.
        </p>
        <div className="cards-grid">
          {cards.map((c, i) => (
            <motion.div
              key={i}
              className="feat-card"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1, duration: 0.5 }}
            >
              <div className="feat-card-icon">{c.icon}</div>
              <div className="feat-card-title">{c.title}</div>
              <div className="feat-card-body">{c.body}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </Panel>
  )
}

export function InfraSection({ active }) {
  const items = [
    'Distributed Edge Computing Network',
    'Zero-latency API Gateway Architecture',
    'Self-healing Microservice Mesh',
    'Encrypted Multi-region Data Fabric',
    'Autonomous Failover & Recovery Systems',
  ]

  return (
    <Panel active={active}>
      <div className="panel-inner right">
        <div className="panel-eyebrow">Section 04 — Digital Infrastructure</div>
        <h2 className="panel-title">
          Built for<br /><em>Scale</em>
        </h2>
        <p className="panel-body">
          A global network of interconnected nodes, data streams, and
          intelligent routing fabric — designed to never fail.
        </p>
        <ul className="infra-list">
          {items.map((item, i) => (
            <motion.li
              key={i}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08, duration: 0.45 }}
            >
              {item}
            </motion.li>
          ))}
        </ul>
        <div className="metrics-row" style={{ marginTop: 28 }}>
          <div>
            <div className="metric-val">128</div>
            <div className="metric-label">Global Nodes</div>
          </div>
          <div>
            <div className="metric-val">40Gb</div>
            <div className="metric-label">Throughput</div>
          </div>
        </div>
      </div>
    </Panel>
  )
}

export function CTASection({ active }) {
  return (
    <Panel active={active}>
      <div className="panel-inner center" style={{ textAlign: 'center' }}>
        <div className="panel-eyebrow">AST Nexus — Ready</div>
        <h2 className="cta-title">
          Build the Future<br />with <em>AST Nexus</em>
        </h2>
        <p className="cta-sub">
          Connect your systems. Deploy intelligence. Enter the Nexus.
        </p>
        <a href="../frontend/index.html" className="cta-btn">
          Enter the Nexus
        </a>
      </div>
    </Panel>
  )
}
