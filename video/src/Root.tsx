import React from 'react';
import {Composition} from 'remotion';
import {FincaRadarVideo, TOTAL} from './Video';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="FincaRadarComercial"
    component={FincaRadarVideo}
    durationInFrames={TOTAL}
    fps={30}
    width={1920}
    height={1080}
  />
);
