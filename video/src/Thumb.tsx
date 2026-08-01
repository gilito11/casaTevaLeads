import React from 'react';
import {AbsoluteFill} from 'remotion';
import {COLORS, FONTS} from './brand';
import {GridBg, RadarMark} from './components';

export const Thumb: React.FC = () => (
  <AbsoluteFill>
    <GridBg dark />
    <AbsoluteFill
      style={{
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
      }}
    >
      <div style={{display: 'flex', alignItems: 'center', gap: 28}}>
        <RadarMark size={92} />
        <div
          style={{
            fontFamily: FONTS.display,
            fontWeight: 900,
            fontSize: 84,
            color: COLORS.papel,
            letterSpacing: '-0.02em',
          }}
        >
          FincaRadar
        </div>
      </div>
      <div
        style={{
          fontFamily: FONTS.display,
          fontWeight: 700,
          fontSize: 40,
          color: '#7EB0FF',
          marginTop: 36,
        }}
      >
        Leads de particulares en tu lista, cada mañana
      </div>
      <div
        style={{
          fontFamily: FONTS.mono,
          fontSize: 24,
          color: 'rgba(242,245,250,0.65)',
          marginTop: 26,
        }}
      >
        5 portales · fuera agencias · scoring 0-90 · fincaradar.com
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);
