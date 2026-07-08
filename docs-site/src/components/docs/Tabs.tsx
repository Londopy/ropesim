'use client';

import { Children, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

export default function Tabs({
  labels,
  children,
}: {
  labels: string[];
  children: React.ReactNode;
}) {
  const [active, setActive] = useState(0);
  const panels = Children.toArray(children);

  return (
    <div className="my-5">
      <div className="flex gap-1 border-b border-line">
        {labels.map((label, i) => (
          <button
            key={label}
            onClick={() => setActive(i)}
            className={`-mb-px border-b-2 px-3 py-1.5 font-heading text-sm transition-colors ${
              i === active
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-body'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={active}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.16 }}
        >
          {panels[active]}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
