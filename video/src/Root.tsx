import React from 'react';
import {Composition} from 'remotion';
import {FincaRadarVideo, TOTAL} from './Video';
import {Thumb} from './Thumb';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="FincaRadarComercial"
      component={FincaRadarVideo}
      durationInFrames={TOTAL}
      fps={30}
      width={1920}
      height={1080}
    />
    <Composition
      id="Miniatura"
      component={Thumb}
      durationInFrames={1}
      fps={30}
      width={1200}
      height={627}
    />
  </>
);
