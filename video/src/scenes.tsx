import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  spring,
} from 'remotion';
import {COLORS, FONTS, PORTALES} from './brand';
import {
  FadeIn,
  GridBg,
  Kicker,
  LeadCard,
  Pop,
  PortalChip,
  RadarMark,
} from './components';

const PAD = 140;

const H1: React.FC<{children: React.ReactNode; dark?: boolean; size?: number}> = ({
  children,
  dark,
  size = 92,
}) => (
  <h1
    style={{
      fontFamily: FONTS.display,
      fontWeight: 900,
      fontSize: size,
      lineHeight: 1.05,
      color: dark ? COLORS.papel : COLORS.tinta,
      margin: 0,
      letterSpacing: '-0.02em',
    }}
  >
    {children}
  </h1>
);

const Sub: React.FC<{children: React.ReactNode; dark?: boolean}> = ({
  children,
  dark,
}) => (
  <p
    style={{
      fontFamily: FONTS.text,
      fontWeight: 400,
      fontSize: 38,
      lineHeight: 1.45,
      color: dark ? 'rgba(242,245,250,0.78)' : COLORS.tinta2,
      margin: '36px 0 0',
      maxWidth: 1150,
    }}
  >
    {children}
  </p>
);

// ---------------- 1 · HOOK ----------------
export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const stamp = 'Publicado ayer · 23:41';
  const chars = Math.floor(
    interpolate(frame, [10, 55], [0, stamp.length], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    })
  );
  return (
    <AbsoluteFill>
      <GridBg dark />
      <AbsoluteFill
        style={{
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 42,
            color: 'rgba(242,245,250,0.6)',
            height: 60,
          }}
        >
          {stamp.slice(0, chars)}
          <span style={{opacity: frame % 20 < 10 ? 1 : 0}}>▌</span>
        </div>
        <FadeIn from={70} duration={22} y={40}>
          <H1 dark size={120}>
            En tu lista
            <br />
            de las 08:00.
          </H1>
        </FadeIn>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------- 2 · PROBLEMA ----------------
export const Problema: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill>
      <GridBg />
      <AbsoluteFill style={{padding: PAD, justifyContent: 'center'}}>
        <FadeIn from={0}>
          <Kicker>Cada mañana, en tu oficina</Kicker>
          <H1>
            Cinco portales.
            <br />
            Cientos de anuncios. Casi todo, agencias.
          </H1>
          <Sub>
            Cuando tu equipo termina de filtrar, los mejores pisos de particular
            ya tienen la primera visita. De otra inmobiliaria.
          </Sub>
        </FadeIn>
        <div style={{display: 'flex', gap: 28, marginTop: 72, flexWrap: 'wrap'}}>
          {PORTALES.map((p, i) => {
            const s = spring({
              frame: frame - 45 - i * 7,
              fps,
              config: {damping: 13, mass: 0.6},
            });
            return (
              <div
                key={p}
                style={{
                  transform: `translateY(${(1 - s) * 60}px)`,
                  opacity: s,
                }}
              >
                <PortalChip name={p} />
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------- 3 · BARRIDO ----------------
export const Barrido: React.FC = () => {
  const frame = useCurrentFrame();
  const revisados = Math.floor(
    interpolate(frame, [60, 320], [0, 1240], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    })
  );
  return (
    <AbsoluteFill>
      <GridBg />
      <AbsoluteFill style={{padding: `${PAD - 40}px ${PAD}px`, justifyContent: 'flex-start'}}>
        <FadeIn from={0}>
          <Kicker>Cada madrugada, sin excepción</Kicker>
          <H1>Cinco portales, un solo barrido.</H1>
          <Sub>
            Tus comerciales no abren cinco pestañas cada mañana. La máquina lo
            hace por ellos: portal a portal, anuncio a anuncio.
          </Sub>
        </FadeIn>
        <div
          style={{
            display: 'flex',
            gap: 24,
            marginTop: 64,
            justifyContent: 'center',
          }}
        >
          {PORTALES.map((p, i) => (
            <FadeIn key={p} from={30 + i * 5} y={24}>
              <PortalChip name={p} style={{fontSize: 26, padding: '14px 26px'}} />
            </FadeIn>
          ))}
        </div>
        {/* flujo de anuncios cayendo al colector */}
        <div style={{position: 'relative', height: 240}}>
          {Array.from({length: 15}).map((_, i) => {
            const col = i % 5;
            const t =
              ((frame - 70 - i * 9) % 90) / 90;
            const visible = frame > 70 + i * 9;
            if (!visible || t < 0) return null;
            const x = 210 + col * 310;
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: x,
                  top: t * 200,
                  width: 18,
                  height: 24,
                  borderRadius: 4,
                  background: COLORS.azul,
                  opacity: 0.85 * (1 - t * 0.4),
                }}
              />
            );
          })}
        </div>
        <FadeIn from={60} y={20}>
          <div
            style={{
              alignSelf: 'center',
              display: 'flex',
              alignItems: 'center',
              gap: 28,
              background: COLORS.tinta,
              borderRadius: 20,
              padding: '26px 44px',
              margin: '0 auto',
              width: 'fit-content',
              boxShadow: '0 24px 60px rgba(12,29,58,0.28)',
            }}
          >
            <RadarMark size={64} />
            <div
              style={{
                fontFamily: FONTS.mono,
                fontSize: 34,
                color: COLORS.papel,
              }}
            >
              anuncios revisados esta noche:{' '}
              <span style={{color: '#7EB0FF', fontWeight: 500}}>
                {revisados.toLocaleString('es-ES')}
              </span>
            </div>
          </div>
        </FadeIn>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------- 4 · FILTRO ----------------
export const Filtro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const caida = spring({frame: frame - 130, fps, config: {damping: 11, mass: 0.9}});
  const fusion = spring({frame: frame - 220, fps, config: {damping: 14}});
  return (
    <AbsoluteFill>
      <GridBg />
      <AbsoluteFill style={{padding: PAD, justifyContent: 'center'}}>
        <FadeIn from={0}>
          <Kicker>El filtro trabaja antes que tú</Kicker>
          <H1>Fuera agencias. Fuera duplicados.</H1>
          <Sub>
            Cada tarjeta que llega a tu lista es un propietario particular, una
            sola vez.
          </Sub>
        </FadeIn>
        <div style={{display: 'flex', gap: 60, marginTop: 80, alignItems: 'flex-start'}}>
          {/* tarjeta agencia que cae */}
          <div
            style={{
              transform: `translateY(${caida * 500}px) rotate(${caida * 10}deg)`,
              opacity: 1 - caida * 0.9,
            }}
          >
            <Pop from={50}>
              <LeadCard
                titulo="Piso reformado en el centro"
                meta="Reus · 145.000 € · 84 m² · «Ref. 4482»"
                badge={{text: 'AGENCIA', color: COLORS.rojo}}
              />
            </Pop>
          </div>
          {/* dos portales, un solo lead */}
          <div style={{position: 'relative', width: 620}}>
            <div
              style={{
                position: 'absolute',
                top: fusion * 0,
                transform: `translateY(${(1 - fusion) * 0}px)`,
              }}
            >
              <Pop from={80}>
                <LeadCard
                  titulo="Casa con jardín, Cambrils"
                  meta="265.000 € · 148 m² · Fotocasa"
                  style={{
                    opacity: 1,
                  }}
                />
              </Pop>
            </div>
            <div
              style={{
                position: 'absolute',
                top: interpolate(fusion, [0, 1], [130, 0]),
                opacity: 1 - fusion,
              }}
            >
              <Pop from={95}>
                <LeadCard
                  titulo="Casa con jardín, Cambrils"
                  meta="265.000 € · 148 m² · Habitaclia"
                />
              </Pop>
            </div>
            <div
              style={{
                position: 'absolute',
                top: 130,
                opacity: fusion,
                transform: `translateY(${(1 - fusion) * 16}px)`,
              }}
            >
              <div
                style={{
                  fontFamily: FONTS.mono,
                  fontSize: 26,
                  color: COLORS.verde,
                  background: 'rgba(22,163,74,0.09)',
                  border: `1.5px solid rgba(22,163,74,0.4)`,
                  borderRadius: 12,
                  padding: '14px 22px',
                  width: 'fit-content',
                }}
              >
                ✓ 1 lead · 2 portales · fusionado
              </div>
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------- 5 · SCORING ----------------
export const Scoring: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <GridBg />
      <AbsoluteFill style={{padding: PAD, justifyContent: 'center'}}>
        <FadeIn from={0}>
          <Kicker>Ordenada por datos, no por intuición</Kicker>
          <H1>Cada lead, puntuado de 0 a 90.</H1>
          <Sub>
            Días en mercado, teléfono, fotos, precio. Los mismos criterios para
            todos los leads, todas las mañanas.
          </Sub>
        </FadeIn>
        <div style={{display: 'flex', flexDirection: 'column', gap: 26, marginTop: 64}}>
          <Pop from={55}>
            <LeadCard
              titulo="Piso 3 hab con terraza, Salou"
              meta="182.000 € · 92 m² · part. · tel. ✓"
              score={82}
              width={880}
            />
          </Pop>
          <Pop from={75}>
            <LeadCard
              titulo="Ático vistas al mar, Torredembarra"
              meta="235.000 € · 88 m² · part. · 12 fotos"
              score={67}
              width={880}
            />
          </Pop>
          <Pop from={95}>
            <LeadCard
              titulo="Casa adosada, Vila-seca"
              meta="248.000 € · 155 m² · part."
              score={41}
              width={880}
            />
          </Pop>
        </div>
        <FadeIn from={140} y={24} style={{marginTop: 44}}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 20,
              fontFamily: FONTS.mono,
              fontSize: 30,
              color: COLORS.rojo,
              width: 'fit-content',
              background: 'rgba(220,38,38,0.07)',
              border: '1.5px solid rgba(220,38,38,0.35)',
              borderRadius: 14,
              padding: '18px 30px',
              opacity: frame > 140 ? 1 : 0,
            }}
          >
            ▼ Bajada del 6% detectada esta noche: tu equipo, avisado al momento.
          </div>
        </FadeIn>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------- 6 · CRM ----------------
const ESTADOS: Record<string, string> = {
  NUEVO: COLORS.azul,
  INTERESADO: COLORS.verde,
  'EN PROCESO': COLORS.ambar,
};

export const Crm: React.FC = () => {
  const filas = [
    {tarea: 'Llamar', lead: 'Piso 3 hab, Salou', estado: 'NUEVO', hora: '08:05'},
    {tarea: 'Visita valoración', lead: 'Casa jardín, Cambrils', estado: 'INTERESADO', hora: '10:30'},
    {tarea: 'Seguimiento', lead: 'Ático, Torredembarra', estado: 'EN PROCESO', hora: '12:00'},
  ];
  const extras = [
    'Estados y agenda comercial',
    'Histórico y bajadas de precio',
    'Mapa de leads por zona',
    'Valoración con comparables (PDF)',
  ];
  return (
    <AbsoluteFill>
      <GridBg />
      <AbsoluteFill style={{padding: `${PAD - 40}px ${PAD}px`, justifyContent: 'center'}}>
        <FadeIn from={0}>
          <Kicker>La entrega</Kicker>
          <H1>Tu lista de la mañana, en tu CRM.</H1>
        </FadeIn>
        <FadeIn from={30} y={40}>
          <div
            style={{
              marginTop: 56,
              background: COLORS.blanco,
              borderRadius: 22,
              border: `1.5px solid ${COLORS.linea}`,
              boxShadow: '0 30px 80px rgba(12,29,58,0.16)',
              overflow: 'hidden',
              width: 1400,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '18px 28px',
                borderBottom: `1.5px solid ${COLORS.linea}`,
                background: COLORS.papel,
              }}
            >
              {['#F87171', '#FBBF24', '#34D399'].map((c) => (
                <div key={c} style={{width: 16, height: 16, borderRadius: 8, background: c}} />
              ))}
              <div
                style={{
                  fontFamily: FONTS.mono,
                  fontSize: 22,
                  color: COLORS.tinta2,
                  marginLeft: 18,
                }}
              >
                fincaradar.com · Agenda del día
              </div>
            </div>
            {filas.map((f, i) => (
              <FadeIn key={f.lead} from={55 + i * 18} y={20}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 28,
                    padding: '26px 34px',
                    borderBottom: `1px solid ${COLORS.linea}`,
                  }}
                >
                  <div
                    style={{
                      fontFamily: FONTS.mono,
                      fontSize: 26,
                      color: COLORS.tinta2,
                      width: 100,
                    }}
                  >
                    {f.hora}
                  </div>
                  <div
                    style={{
                      fontFamily: FONTS.display,
                      fontWeight: 700,
                      fontSize: 30,
                      color: COLORS.tinta,
                      width: 330,
                    }}
                  >
                    {f.tarea}
                  </div>
                  <div
                    style={{
                      fontFamily: FONTS.text,
                      fontSize: 28,
                      color: COLORS.tinta2,
                      flex: 1,
                    }}
                  >
                    {f.lead}
                  </div>
                  <div
                    style={{
                      fontFamily: FONTS.mono,
                      fontSize: 21,
                      letterSpacing: '0.06em',
                      color: COLORS.blanco,
                      background: ESTADOS[f.estado],
                      borderRadius: 9,
                      padding: '8px 16px',
                    }}
                  >
                    {f.estado}
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </FadeIn>
        <div style={{display: 'flex', gap: 22, marginTop: 44, flexWrap: 'wrap'}}>
          {extras.map((e, i) => (
            <FadeIn key={e} from={130 + i * 12} y={18}>
              <div
                style={{
                  fontFamily: FONTS.mono,
                  fontSize: 24,
                  color: COLORS.tinta,
                  background: 'rgba(37,99,235,0.07)',
                  border: `1.5px solid rgba(37,99,235,0.3)`,
                  borderRadius: 12,
                  padding: '14px 24px',
                }}
              >
                {e}
              </div>
            </FadeIn>
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------- 7 · CIERRE ----------------
export const Cierre: React.FC = () => {
  return (
    <AbsoluteFill>
      <GridBg dark />
      <AbsoluteFill
        style={{alignItems: 'center', justifyContent: 'center', textAlign: 'center'}}
      >
        <Pop from={5}>
          <RadarMark size={130} />
        </Pop>
        <FadeIn from={30} y={30} style={{marginTop: 48}}>
          <H1 dark size={104}>
            Tu equipo llama primero.
          </H1>
        </FadeIn>
        <FadeIn from={70} y={24} style={{marginTop: 52}}>
          <div
            style={{
              fontFamily: FONTS.display,
              fontWeight: 700,
              fontSize: 56,
              color: '#7EB0FF',
            }}
          >
            fincaradar.com
          </div>
        </FadeIn>
        <FadeIn from={95} y={20} style={{marginTop: 30}}>
          <div
            style={{
              fontFamily: FONTS.mono,
              fontSize: 32,
              color: 'rgba(242,245,250,0.7)',
            }}
          >
            hola@fincaradar.com · Solicita una demo con tu zona
          </div>
        </FadeIn>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
