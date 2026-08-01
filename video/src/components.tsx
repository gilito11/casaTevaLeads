import React from 'react';
import {interpolate, useCurrentFrame, spring, useVideoConfig} from 'remotion';
import {COLORS, FONTS} from './brand';

export const GridBg: React.FC<{dark?: boolean}> = ({dark}) => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      backgroundColor: dark ? COLORS.tinta : COLORS.papel,
      backgroundImage: dark
        ? `linear-gradient(rgba(199,211,232,.07) 1px, transparent 1px),
           linear-gradient(90deg, rgba(199,211,232,.07) 1px, transparent 1px)`
        : `linear-gradient(rgba(199,211,232,.38) 1px, transparent 1px),
           linear-gradient(90deg, rgba(199,211,232,.38) 1px, transparent 1px)`,
      backgroundSize: '64px 64px',
    }}
  />
);

export const Kicker: React.FC<{children: React.ReactNode; dark?: boolean}> = ({
  children,
  dark,
}) => (
  <div
    style={{
      fontFamily: FONTS.mono,
      fontSize: 26,
      letterSpacing: '0.22em',
      textTransform: 'uppercase',
      color: dark ? 'rgba(242,245,250,0.65)' : COLORS.azul,
      marginBottom: 28,
    }}
  >
    {children}
  </div>
);

export const FadeIn: React.FC<{
  from?: number;
  duration?: number;
  y?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({from = 0, duration = 20, y = 34, children, style}) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [from, from + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        opacity: t,
        transform: `translateY(${(1 - t) * y}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Pop: React.FC<{
  from?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({from = 0, children, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: frame - from, fps, config: {damping: 14, mass: 0.7}});
  return (
    <div style={{transform: `scale(${s})`, opacity: s > 0.05 ? 1 : 0, ...style}}>
      {children}
    </div>
  );
};

export const SceneFade: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
}> = ({durationInFrames, children}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, 12, durationInFrames - 12, durationInFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  return <div style={{position: 'absolute', inset: 0, opacity}}>{children}</div>;
};

export const RadarMark: React.FC<{size?: number}> = ({size = 96}) => (
  <div
    style={{
      width: size,
      height: size,
      borderRadius: size * 0.25,
      background: COLORS.azul,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}
  >
    <svg
      viewBox="0 0 32 32"
      width={size * 0.72}
      height={size * 0.72}
      fill="none"
    >
      <circle cx="10" cy="22" r="2" fill="#5EEAD4" />
      <path
        d="M10 15a7 7 0 0 1 7 7"
        stroke="#5EEAD4"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M10 9a13 13 0 0 1 13 13"
        stroke="#5EEAD4"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="18" cy="14" r="2.4" fill="#5EEAD4" />
    </svg>
  </div>
);

export const PortalChip: React.FC<{name: string; style?: React.CSSProperties}> = ({
  name,
  style,
}) => (
  <div
    style={{
      fontFamily: FONTS.mono,
      fontSize: 30,
      color: COLORS.tinta,
      background: COLORS.blanco,
      border: `2px solid ${COLORS.linea}`,
      borderRadius: 14,
      padding: '18px 34px',
      boxShadow: '0 10px 28px rgba(12,29,58,0.10)',
      ...style,
    }}
  >
    {name}
  </div>
);

export const LeadCard: React.FC<{
  titulo: string;
  meta: string;
  score?: number;
  badge?: {text: string; color: string};
  width?: number;
  style?: React.CSSProperties;
}> = ({titulo, meta, score, badge, width = 560, style}) => (
  <div
    style={{
      width,
      background: COLORS.blanco,
      borderRadius: 18,
      border: `1.5px solid ${COLORS.linea}`,
      boxShadow: '0 16px 40px rgba(12,29,58,0.12)',
      padding: '28px 32px',
      display: 'flex',
      alignItems: 'center',
      gap: 24,
      ...style,
    }}
  >
    <div style={{flex: 1, minWidth: 0}}>
      <div
        style={{
          fontFamily: FONTS.display,
          fontWeight: 700,
          fontSize: 32,
          color: COLORS.tinta,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {titulo}
      </div>
      <div
        style={{
          fontFamily: FONTS.mono,
          fontSize: 24,
          color: COLORS.tinta2,
          marginTop: 8,
        }}
      >
        {meta}
      </div>
    </div>
    {badge ? (
      <div
        style={{
          fontFamily: FONTS.mono,
          fontSize: 22,
          letterSpacing: '0.08em',
          color: COLORS.blanco,
          background: badge.color,
          borderRadius: 10,
          padding: '10px 18px',
          flexShrink: 0,
        }}
      >
        {badge.text}
      </div>
    ) : null}
    {typeof score === 'number' ? (
      <div
        style={{
          width: 84,
          height: 84,
          borderRadius: 42,
          border: `4px solid ${score >= 60 ? COLORS.verde : score >= 35 ? COLORS.ambar : COLORS.linea}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: FONTS.display,
          fontWeight: 900,
          fontSize: 34,
          color: COLORS.tinta,
          flexShrink: 0,
        }}
      >
        {score}
      </div>
    ) : null}
  </div>
);
