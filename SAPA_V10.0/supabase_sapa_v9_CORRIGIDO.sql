-- ================================================================
-- SAPA v9.0 — Banco Supabase CORRIGIDO
-- Correções aplicadas vs. versão anterior:
--   1. grade_horarios.dia_semana: INTEGER → TEXT  (compatível com calendar_engine.py)
--   2. logs.ra_aluno: ON DELETE RESTRICT → ON DELETE SET NULL  (permite excluir alunos)
--   3. logs: coluna "hora TEXT" adicionada  (usada por faltas automáticas e sync)
-- Cole TUDO no SQL Editor do Supabase e clique em RUN
-- ================================================================

-- Limpa tudo na ordem certa (CASCADE cuida das FKs)
DROP TABLE IF EXISTS public.sync_queue     CASCADE;
DROP TABLE IF EXISTS public.logs           CASCADE;
DROP TABLE IF EXISTS public.grade_horarios CASCADE;
DROP TABLE IF EXISTS public.disciplinas    CASCADE;
DROP TABLE IF EXISTS public.professores    CASCADE;
DROP TABLE IF EXISTS public.alunos         CASCADE;
DROP VIEW  IF EXISTS public.vw_presenca;

-- ── 1. ALUNOS ─────────────────────────────────────────────────────────────────
CREATE TABLE public.alunos (
    ra        INTEGER PRIMARY KEY,
    nome      TEXT    NOT NULL,
    turma     TEXT    NOT NULL,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);

-- ── 2. PROFESSORES ────────────────────────────────────────────────────────────
CREATE TABLE public.professores (
    id             SERIAL PRIMARY KEY,
    nome_professor TEXT    NOT NULL UNIQUE,
    email          TEXT,
    telefone       TEXT,
    senha_hash     TEXT,
    is_admin       BOOLEAN DEFAULT FALSE,
    criado_em      TIMESTAMPTZ DEFAULT NOW()
);

-- ── 3. DISCIPLINAS ────────────────────────────────────────────────────────────
CREATE TABLE public.disciplinas (
    id             SERIAL PRIMARY KEY,
    nome_materia   TEXT,
    professor_nome TEXT,
    semestre       TEXT,
    bloco          TEXT,
    data_inicio    TEXT,
    data_fim       TEXT,
    dia_semana     TEXT,   -- "Segunda-feira", "Terça-feira" … "Domingo"
    criado_em      TIMESTAMPTZ DEFAULT NOW()
);

-- ── 4. GRADE DE HORÁRIOS ──────────────────────────────────────────────────────
CREATE TABLE public.grade_horarios (
    id            SERIAL PRIMARY KEY,
    disciplina_id INTEGER REFERENCES public.disciplinas(id) ON DELETE CASCADE,
    -- CORREÇÃO 1: era INTEGER (0-6). Agora TEXT para bater com calendar_engine.py
    -- que salva "Segunda-feira", "Terça-feira" etc.
    dia_semana    TEXT,
    hora_inicio   TEXT,
    hora_fim      TEXT,
    turma         TEXT,
    criado_em     TIMESTAMPTZ DEFAULT NOW()
);

-- ── 5. LOGS DE PRESENÇA ───────────────────────────────────────────────────────
CREATE TABLE public.logs (
    id            BIGSERIAL PRIMARY KEY,
    -- CORREÇÃO 2: era ON DELETE RESTRICT — impedia excluir alunos com histórico.
    -- SET NULL preserva o log mas desvincula o aluno excluído.
    ra_aluno      INTEGER REFERENCES public.alunos(ra) ON DELETE SET NULL,
    data          TEXT,
    -- CORREÇÃO 3: coluna "hora" faltava. Usada por faltas automáticas e sync_manager.
    hora          TEXT,
    hora_entrada  TEXT,
    hora_saida    TEXT,
    disciplina    TEXT,
    tipo          TEXT CHECK (tipo IN ('ENTRADA','SAIDA','FALTA','JUSTIFICADO')),
    justificativa TEXT,
    registrado_em TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para queries do Power BI (filtros por data, aluno e status)
CREATE INDEX idx_logs_data ON public.logs(data);
CREATE INDEX idx_logs_ra   ON public.logs(ra_aluno);
CREATE INDEX idx_logs_tipo ON public.logs(tipo);

-- ── 6. FILA DE SYNC ───────────────────────────────────────────────────────────
CREATE TABLE public.sync_queue (
    id         BIGSERIAL PRIMARY KEY,
    payload    JSONB       NOT NULL,
    tentativas SMALLINT    DEFAULT 0,
    enviado    BOOLEAN     DEFAULT FALSE,
    criado_em  TIMESTAMPTZ DEFAULT NOW()
);

-- ── 7. RLS — libera service_role (chave usada pelo Python) ───────────────────
ALTER TABLE public.alunos         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.professores    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.disciplinas    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.grade_horarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.logs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_queue     ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all" ON public.alunos         USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON public.professores    USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON public.disciplinas    USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON public.grade_horarios USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON public.logs           USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON public.sync_queue     USING (true) WITH CHECK (true);

-- ── 8. VIEW PARA POWER BI ────────────────────────────────────────────────────
-- Conecte direto a esta view no Power BI: fica muito mais simples.
CREATE OR REPLACE VIEW public.vw_presenca AS
SELECT
    l.id            AS log_id,
    l.data,
    l.hora,
    l.hora_entrada,
    l.hora_saida,
    l.tipo          AS status,
    l.justificativa,
    l.disciplina,
    l.registrado_em,
    a.ra,
    a.nome          AS aluno_nome,
    a.turma,
    d.nome_materia,
    d.semestre,
    d.bloco,
    d.data_inicio   AS disciplina_inicio,
    d.data_fim      AS disciplina_fim,
    p.nome_professor AS professor
FROM public.logs l
LEFT JOIN public.alunos      a ON a.ra = l.ra_aluno
LEFT JOIN public.disciplinas d
    ON  d.nome_materia   || ' - '
     || d.semestre       || ' ('
     || d.bloco          || ') - '
     || d.professor_nome = l.disciplina
LEFT JOIN public.professores p ON p.nome_professor = d.professor_nome;

-- ── 9. ALUNOS INICIAIS ────────────────────────────────────────────────────────
INSERT INTO public.alunos (ra, nome, turma) VALUES
(16152,'Allan Victor Braga Dias','A'),
(16304,'Ana Livia Almeida Ramos','A'),
(16182,'Arthur Belotte Isensee','A'),
(16203,'Davi Mateus Miranda de Albuquerque','A'),
(16183,'Douglas Leonardo de Paiva Costa','A'),
(16279,'Joao Lucas Manoel Paes','A'),
(16369,'Joao Vitor Gadbem Silva','A'),
(16191,'Lemuel Baruc Silva Souza','A'),
(16301,'Lucas de Freitas Alves','A'),
(16284,'Maria Rita Chaves da Silva','A'),
(16266,'Thales Calheiros','A'),
(16448,'Yuri Neves Rocha Roque','A'),
(16067,'Ana Carolina Valim Faria','B'),
(15903,'Benaiah James Putz','B'),
(15811,'Carlos Alexandre Bastos Xavier','B'),
(15793,'Gabriel Augusto de Assis Bonifacio','B'),
(15833,'Gabriel Lucas da Silva Oliveira','B'),
(16080,'Gabriel Miguel Cordeiro','B'),
(15712,'Guilherme Augusto Moreira Fedrizzi','B'),
(15652,'Joao Pedro Faria das Neves da Silva','B'),
(15987,'Kauan Felipe de Faria','B'),
(15809,'Lucas Amaro Ribeiro e Silva','B'),
(16061,'Lucas Eliziario Silva Marques','B'),
(15704,'Luis Gustavo Bonifacio','B'),
(16035,'Matheus Lopes Dias Claudino','B'),
(16017,'Nalberto Pereira Jesus','B'),
(15888,'Naomi Marra Marcondes Ribeiro','B'),
(15805,'Otavio Henrique Bastos de Souza','B'),
(15964,'Vicente Augusto Ribeiro Rosa','B'),
(15650,'Washington Vicente da Silva','B'),
(15947,'Wesley Jesus de Souza Campos','B'),
(15313,'Lucas Lima Barboza','C'),
(15482,'Bruno Alexandre de Oliveira','C'),
(15568,'Davi Rodarte de Souza Junior','C'),
(15421,'Gustavo da Silva Carvalho','C'),
(15312,'Gustavo Moreira da Silva','C'),
(15390,'Gustavo Souza Silva','C'),
(15370,'Hugo Andre Castor Silva','C'),
(15426,'Joao David Cattermol Cabizuca','C'),
(15565,'Jose Pedro Silverio Assis','C'),
(11868,'Jose Vagner Pereira Junior','C'),
(15294,'Karla Rodrigues de Sousa','C'),
(15280,'Mateus Henrique Delfino','C'),
(9053, 'Pedro Vilela Maciel','C'),
(15140,'Raquel Taveira de Oliveira','C')
ON CONFLICT (ra) DO UPDATE SET nome = EXCLUDED.nome, turma = EXCLUDED.turma;

-- ── 10. PROFESSOR INICIAL ─────────────────────────────────────────────────────
INSERT INTO public.professores (nome_professor, email, senha_hash) VALUES
('Juliano Lopes', 'teste123@gmail.com',
 '$2b$12$AYP0uEd8Jj/c96U/MW3lAe3uFM1rWuCEEMvpPCzoxBOUAP8XjaRzu')
ON CONFLICT (nome_professor) DO UPDATE SET email = EXCLUDED.email;

-- ── VERIFICAÇÃO FINAL ─────────────────────────────────────────────────────────
SELECT
    'alunos'         AS tabela, COUNT(*) AS registros FROM public.alunos
UNION ALL SELECT 'professores',    COUNT(*) FROM public.professores
UNION ALL SELECT 'disciplinas',    COUNT(*) FROM public.disciplinas
UNION ALL SELECT 'grade_horarios', COUNT(*) FROM public.grade_horarios
UNION ALL SELECT 'logs',           COUNT(*) FROM public.logs;
