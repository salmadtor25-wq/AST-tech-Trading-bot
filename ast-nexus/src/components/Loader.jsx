import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function Loader({ onComplete }) {
  const [progress, setProgress] = useState(0)
  const [done, setDone] = useState(false)

  useEffect(() => {
    const steps = [
      { target: 25, delay: 120 },
      { target: 55, delay: 90  },
      { target: 80, delay: 70  },
      { target: 95, delay: 60  },
      { target: 100, delay: 40 },
    ]
    let current = 0
    let pct = 0

    function tick() {
      const step = steps[current]
      if (!step) return

      const interval = setInterval(() => {
        pct += 1
        setProgress(pct)
        if (pct >= step.target) {
          clearInterval(interval)
          current++
          if (current < steps.length) {
            setTimeout(tick, 80)
          } else {
            setTimeout(() => {
              setDone(true)
              setTimeout(onComplete, 600)
            }, 300)
          }
        }
      }, step.delay)
    }
    tick()
  }, [onComplete])

  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          className="loader"
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6 }}
        >
          <motion.div
            className="loader-logo"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            AST Nexus
            <span>Initializing Digital Core</span>
          </motion.div>

          <div className="loader-ring" />

          <div className="loader-bar-wrap">
            <div className="loader-bar" style={{ width: `${progress}%` }} />
          </div>

          <motion.div
            className="loader-pct"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            {progress}%
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
