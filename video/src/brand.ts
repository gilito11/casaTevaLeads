import {loadFont as loadArchivo} from '@remotion/google-fonts/Archivo';
import {loadFont as loadInstrument} from '@remotion/google-fonts/InstrumentSans';
import {loadFont as loadMono} from '@remotion/google-fonts/SplineSansMono';

const archivo = loadArchivo('normal', {weights: ['500', '700', '900']});
const instrument = loadInstrument('normal', {weights: ['400', '500', '600']});
const mono = loadMono('normal', {weights: ['400', '500']});

export const COLORS = {
  papel: '#F2F5FA',
  blanco: '#FFFFFF',
  tinta: '#0C1D3A',
  tinta2: '#4A5A75',
  azul: '#2563EB',
  azulOscuro: '#1D4ED8',
  verde: '#16A34A',
  rojo: '#DC2626',
  ambar: '#D97706',
  linea: '#C7D3E8',
};

export const FONTS = {
  display: `${archivo.fontFamily}, sans-serif`,
  text: `${instrument.fontFamily}, sans-serif`,
  mono: `${mono.fontFamily}, monospace`,
};

export const PORTALES = [
  'Idealista',
  'Fotocasa',
  'Habitaclia',
  'Milanuncios',
  'Wallapop',
];
