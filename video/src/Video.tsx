import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {COLORS} from './brand';
import {SceneFade} from './components';
import {Barrido, Cierre, Crm, Filtro, Hook, Problema, Scoring} from './scenes';

export const DUR = {
  hook: 180,
  problema: 240,
  barrido: 360,
  filtro: 360,
  scoring: 360,
  crm: 420,
  cierre: 330,
};

export const TOTAL = Object.values(DUR).reduce((a, b) => a + b, 0);

export const FincaRadarVideo: React.FC = () => {
  const scenes: Array<[number, React.FC]> = [
    [DUR.hook, Hook],
    [DUR.problema, Problema],
    [DUR.barrido, Barrido],
    [DUR.filtro, Filtro],
    [DUR.scoring, Scoring],
    [DUR.crm, Crm],
    [DUR.cierre, Cierre],
  ];
  let from = 0;
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.tinta}}>
      {scenes.map(([dur, Scene], i) => {
        const el = (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <SceneFade durationInFrames={dur}>
              <Scene />
            </SceneFade>
          </Sequence>
        );
        from += dur;
        return el;
      })}
    </AbsoluteFill>
  );
};
