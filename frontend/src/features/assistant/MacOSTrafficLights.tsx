import React from 'react';

interface MacOSTrafficLightsProps {
  onClose: () => void;
  onMinimize: () => void;
  onMaximizeToggle: () => void;
  isMaximized: boolean;
}

export const MacOSTrafficLights: React.FC<MacOSTrafficLightsProps> = ({
  onClose,
  onMinimize,
  onMaximizeToggle,
  isMaximized,
}) => {
  return (
    <div className="macos-traffic-lights" role="group" aria-label="Window controls">
      {/* Red: Close */}
      <button
        type="button"
        className="traffic-light close"
        onClick={onClose}
        aria-label="Close assistant"
        title="Close (Esc)"
      >
        <span className="light-symbol" aria-hidden="true">
          <svg width="7" height="7" viewBox="0 0 7 7" fill="none">
            <path
              d="M1 1L6 6M6 1L1 6"
              stroke="#4c0000"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
          </svg>
        </span>
      </button>

      {/* Yellow: Minimize to launcher */}
      <button
        type="button"
        className="traffic-light minimize"
        onClick={onMinimize}
        aria-label="Minimize assistant to launcher"
        title="Minimize to launcher"
      >
        <span className="light-symbol" aria-hidden="true">
          <svg width="7" height="2" viewBox="0 0 7 2" fill="none">
            <path
              d="M0.5 1H6.5"
              stroke="#593b00"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
          </svg>
        </span>
      </button>

      {/* Green: Maximize / Restore */}
      <button
        type="button"
        className="traffic-light maximize"
        onClick={onMaximizeToggle}
        aria-label={isMaximized ? 'Restore window size' : 'Maximize window'}
        title={isMaximized ? 'Restore window size' : 'Maximize window'}
      >
        <span className="light-symbol" aria-hidden="true">
          {isMaximized ? (
            <svg width="7" height="7" viewBox="0 0 7 7" fill="none">
              <path
                d="M5 2V5H2M2 5L6 1M2 2H5"
                stroke="#003e08"
                strokeWidth="1"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          ) : (
            <svg width="6" height="6" viewBox="0 0 6 6" fill="none">
              <path
                d="M0.5 5.5L5.5 0.5M5.5 3.5V0.5H2.5"
                stroke="#003e08"
                strokeWidth="1.1"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </span>
      </button>
    </div>
  );
};
