-- =====================================================================
-- Portal del Trabajador · Esquema de Supabase (Postgres)
-- Se puede ejecutar varias veces: crea lo que falta y reemplaza funciones,
-- triggers y políticas. Pegar completo en el SQL Editor de Supabase.
-- =====================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- Utilidad: updated_at automático
-- ---------------------------------------------------------------------
create or replace function public.tocar_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end; $$;

-- ---------------------------------------------------------------------
-- Perfil (1 a 1 con auth.users)
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  nombre_completo text,
  cedula text,
  email text,
  rol text not null default 'trabajador' check (rol in ('trabajador','admin')),
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, nombre_completo)
  values (new.id, new.email, new.raw_user_meta_data->>'nombre_completo');
  return new;
end; $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------
-- Contrato / minuta del trabajador
-- ---------------------------------------------------------------------
create table if not exists public.contratos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  numero_contrato text,
  entidad text,
  tipo_contratacion text not null default 'prestacion_servicios'
    check (tipo_contratacion in ('prestacion_servicios','practica_formativa','otro')),
  proyecto text,
  objeto text,
  dependencia text,
  supervisor_nombre text,
  supervisor_cargo text,
  fecha_contrato date,          -- fecha de suscripción (la pide la plantilla oficial)
  fecha_inicio date,
  fecha_fin date,
  plazo_texto text,
  valor_total numeric,
  forma_pago text,
  minuta_path text,             -- ruta en Storage
  texto_extraido text,
  datos_json jsonb,             -- respuesta completa de la IA
  activo boolean not null default true,
  created_at timestamptz not null default now()
);
alter table public.contratos add column if not exists fecha_contrato date;
alter table public.contratos add column if not exists cedula_contratista text;  -- verificada en el texto de la minuta
create unique index if not exists one_active_contract_per_user
  on public.contratos(user_id) where activo;

-- ---------------------------------------------------------------------
-- Obligaciones extraídas de la minuta
-- ---------------------------------------------------------------------
create table if not exists public.obligaciones (
  id uuid primary key default gen_random_uuid(),
  contrato_id uuid not null references public.contratos(id) on delete cascade,
  numero int not null,
  tipo text not null default 'especifica' check (tipo in ('especifica','general')),
  texto text not null,
  palabras_clave text[] default '{}',
  unique (contrato_id, numero, tipo)
);

-- ---------------------------------------------------------------------
-- Plantilla oficial de informe en blanco
-- ---------------------------------------------------------------------
create table if not exists public.plantillas_informe (
  id uuid primary key default gen_random_uuid(),
  alcance text not null default 'usuario' check (alcance in ('global','usuario')),
  user_id uuid references public.profiles(id) on delete cascade,
  nombre text not null,
  formato text not null check (formato in ('docx','pdf')),
  archivo_path text not null,
  mapa_campos jsonb,
  activa boolean not null default true,
  created_at timestamptz not null default now(),
  check ((alcance = 'global' and user_id is null) or (alcance = 'usuario' and user_id is not null))
);

-- ---------------------------------------------------------------------
-- Informe (uno por contrato y periodo)
-- ---------------------------------------------------------------------
create table if not exists public.informes (
  id uuid primary key default gen_random_uuid(),
  contrato_id uuid not null references public.contratos(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  plantilla_id uuid references public.plantillas_informe(id),
  periodo_inicio date not null,
  periodo_fin date not null,
  tipo text not null default 'parcial' check (tipo in ('parcial','final')),
  estado text not null default 'borrador' check (estado in ('borrador','finalizado')),
  docx_path text,
  pdf_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (contrato_id, periodo_inicio, periodo_fin)
);
drop trigger if exists informes_updated_at on public.informes;
create trigger informes_updated_at before update on public.informes
  for each row execute function public.tocar_updated_at();

-- ---------------------------------------------------------------------
-- Actividades diarias
-- ---------------------------------------------------------------------
create table if not exists public.actividades (
  id uuid primary key default gen_random_uuid(),
  informe_id uuid not null references public.informes(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  fecha date not null default current_date,
  texto_original text not null,
  texto_redactado text,
  obligacion_id uuid references public.obligaciones(id) on delete set null,
  confianza numeric check (confianza between 0 and 1),
  estado text not null default 'propuesta'
    check (estado in ('propuesta','confirmada','sin_obligacion')),
  modelo_usado text,
  created_at timestamptz not null default now()
);
create index if not exists actividades_informe_obligacion_idx
  on public.actividades(informe_id, obligacion_id);

-- ---------------------------------------------------------------------
-- Evidencias (anexos)
-- ---------------------------------------------------------------------
create table if not exists public.evidencias (
  id uuid primary key default gen_random_uuid(),
  actividad_id uuid not null references public.actividades(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  path text not null,
  nombre text,
  descripcion text,             -- texto del anexo en el informe (lo propone la IA, el usuario lo puede editar)
  created_at timestamptz not null default now()
);
alter table public.evidencias add column if not exists descripcion text;

-- ---------------------------------------------------------------------
-- Registro de llamadas a IA (diagnóstico y costos)
-- ---------------------------------------------------------------------
create table if not exists public.ia_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  tarea text,                 -- 'extraer_minuta' | 'clasificar_actividad' | 'mapear_plantilla'
  modelo text,
  ok boolean,
  ms int,
  tokens_in int,
  tokens_out int,
  error text,
  created_at timestamptz not null default now()
);
alter table public.ia_logs add column if not exists llave text;   -- últimos caracteres de la llave usada

-- =====================================================================
-- Planes, pagos y consumo de informes
-- =====================================================================
create table if not exists public.planes (
  id text primary key,                     -- 'gratis' | 'normal' | 'pro'
  nombre text not null,
  precio_cop integer not null,             -- 0, 15000, 50000 (pesos colombianos)
  informes_limite integer,                 -- null = ilimitados
  periodo_limite text not null check (periodo_limite in ('total','mensual')),
  dias_vigencia integer,                   -- null en el plan gratis; 30 en los de pago
  activo boolean not null default true
);

insert into public.planes (id, nombre, precio_cop, informes_limite, periodo_limite, dias_vigencia) values
  ('gratis', 'Gratis (prueba)', 0,     2,    'total',   null),
  ('normal', 'Normal',          15000, 2,    'mensual', 30),
  ('pro',    'Pro',             50000, null, 'mensual', 30)
on conflict (id) do update set
  nombre = excluded.nombre, precio_cop = excluded.precio_cop,
  informes_limite = excluded.informes_limite, periodo_limite = excluded.periodo_limite,
  dias_vigencia = excluded.dias_vigencia;

create table if not exists public.suscripciones (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  plan_id text not null references public.planes(id),
  estado text not null default 'activa' check (estado in ('activa','vencida','cancelada')),
  inicio timestamptz not null default now(),
  fin timestamptz,                         -- null en el plan gratis
  created_at timestamptz not null default now()
);
create unique index if not exists una_suscripcion_activa
  on public.suscripciones(user_id) where estado = 'activa';

-- Todo usuario nuevo empieza con el plan gratis
create or replace function public.asignar_plan_gratis() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.suscripciones (user_id, plan_id) values (new.id, 'gratis');
  return new;
end; $$;

drop trigger if exists perfil_plan_gratis on public.profiles;
create trigger perfil_plan_gratis after insert on public.profiles
  for each row execute function public.asignar_plan_gratis();

create table if not exists public.pagos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  plan_id text not null references public.planes(id),
  referencia text not null unique,         -- la genera el backend y se envía a la pasarela
  pasarela text not null default 'wompi',
  id_transaccion text,                     -- id que devuelve la pasarela
  monto_cop integer not null,
  estado text not null default 'pendiente'
    check (estado in ('pendiente','aprobado','rechazado','anulado','error')),
  evento_json jsonb,                       -- último evento recibido
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
drop trigger if exists pagos_updated_at on public.pagos;
create trigger pagos_updated_at before update on public.pagos
  for each row execute function public.tocar_updated_at();

create table if not exists public.consumo_informes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  informe_id uuid references public.informes(id) on delete set null,
  plan_id text not null references public.planes(id),
  ciclo text not null,                     -- 'total' (gratis) o 'YYYY-MM' (planes mensuales)
  created_at timestamptz not null default now()
);
create unique index if not exists un_cobro_por_informe
  on public.consumo_informes(informe_id, ciclo);

-- ---------------------------------------------------------------------
-- Cuentas de prueba sin límite de informes ni de solicitudes.
-- Solo el backend las lee (RLS sin políticas). Se agrega una con:
--   insert into public.cuentas_sin_limite (email, nota) values ('correo@ejemplo.com', 'motivo');
-- Aplica solo si el correo está confirmado en Supabase Auth.
-- ---------------------------------------------------------------------
create table if not exists public.cuentas_sin_limite (
  email text primary key check (email = lower(email)),
  nota text,
  created_at timestamptz not null default now()
);
alter table public.cuentas_sin_limite enable row level security;
insert into public.cuentas_sin_limite (email, nota)
  values ('samuelolimiranda@gmail.com', 'Cuenta de pruebas del administrador')
on conflict (email) do nothing;

create or replace function public.es_sin_limite(p_user uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from auth.users u
    join public.cuentas_sin_limite c on c.email = lower(u.email)
    where u.id = p_user and u.email_confirmed_at is not null);
$$;
revoke all on function public.es_sin_limite(uuid) from public, anon, authenticated;
grant execute on function public.es_sin_limite(uuid) to service_role;

-- ---------------------------------------------------------------------
-- Una cédula = una cuenta.
-- La cédula se toma de la minuta (el backend verifica que aparezca en su
-- texto) y queda fija en el perfil: el usuario no la puede cambiar y otra
-- cuenta no puede registrar un contrato con esa misma cédula.
-- Para liberar una cédula (soporte):  update public.profiles set cedula = null where id = '...';
-- ---------------------------------------------------------------------
update public.profiles set cedula = nullif(regexp_replace(cedula, '\D', '', 'g'), '')
  where cedula is not null and cedula ~ '\D';
create unique index if not exists perfil_cedula_unica on public.profiles(cedula) where cedula is not null;

create or replace function public.vincular_cedula(p_user uuid, p_cedula text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_ced text := regexp_replace(coalesce(p_cedula, ''), '\D', '', 'g');
  v_actual text;
  v_correo text;
begin
  if length(v_ced) < 5 or length(v_ced) > 15 then
    return jsonb_build_object('ok', false, 'motivo', 'cedula_invalida');
  end if;
  perform pg_advisory_xact_lock(hashtext('cedula:' || v_ced));
  select cedula into v_actual from public.profiles where id = p_user for update;
  if v_actual is not null and v_actual <> v_ced then
    return jsonb_build_object('ok', false, 'motivo', 'cedula_distinta', 'cedula_cuenta', v_actual);
  end if;
  select email into v_correo from public.profiles where cedula = v_ced and id <> p_user;
  if found then
    return jsonb_build_object('ok', false, 'motivo', 'cedula_en_uso', 'correo', v_correo);
  end if;
  update public.profiles set cedula = v_ced where id = p_user;
  return jsonb_build_object('ok', true, 'cedula', v_ced);
end; $$;
revoke all on function public.vincular_cedula(uuid, text) from public, anon, authenticated;
grant execute on function public.vincular_cedula(uuid, text) to service_role;

-- La prueba gratis es de la persona (cédula), no de la cuenta: borrar la cuenta y crear
-- otra no da 2 informes más. Se guarda solo un hash de la cédula (no la cédula).
create table if not exists public.pruebas_gratis (
  cedula_hash text primary key,
  usados int not null default 0,
  actualizado timestamptz not null default now()
);
alter table public.pruebas_gratis enable row level security;

create or replace function public.hash_cedula(p_cedula text)
returns text language sql immutable set search_path = public as $$
  select encode(sha256(convert_to(p_cedula, 'UTF8')), 'hex');
$$;

create or replace function public.usados_prueba(p_user uuid)
returns int language plpgsql stable security definer set search_path = public as $$
declare
  v_ced text;
  v_por_cedula int := 0;
  v_por_cuenta int;
begin
  select cedula into v_ced from public.profiles where id = p_user;
  if v_ced is not null then
    select usados into v_por_cedula from public.pruebas_gratis where cedula_hash = public.hash_cedula(v_ced);
  end if;
  select count(*) into v_por_cuenta from public.consumo_informes
    where user_id = p_user and ciclo = 'total' and plan_id = 'gratis';
  return greatest(coalesce(v_por_cedula, 0), v_por_cuenta);
end; $$;
revoke all on function public.usados_prueba(uuid) from public, anon, authenticated;
grant execute on function public.usados_prueba(uuid) to service_role;

-- Lecturas de minuta: el texto extraído se queda en el servidor hasta que el
-- usuario confirma el contrato (así el programa no puede enviar un texto inventado).
create table if not exists public.lecturas_minuta (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  minuta_path text not null,
  texto text not null,
  datos jsonb,
  created_at timestamptz not null default now()
);
alter table public.lecturas_minuta enable row level security;

-- ---------------------------------------------------------------------
-- Descuenta un informe del cupo. Solo la llama el backend (service role).
-- El ciclo mensual usa la hora de Colombia.
-- ---------------------------------------------------------------------
create or replace function public.consumir_informe(p_user uuid, p_informe uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_sub public.suscripciones;
  v_plan public.planes;
  v_ciclo text;
  v_usados int;
  v_ced text;
begin
  perform pg_advisory_xact_lock(hashtext(p_user::text));

  -- Cuentas de prueba: siempre se permite y no se descuenta nada
  if public.es_sin_limite(p_user) then
    return jsonb_build_object('permitido', true, 'plan', 'pruebas', 'cobrado', false, 'ciclo', 'pruebas',
                              'sin_limite', true);
  end if;

  -- Una suscripción de pago cuyo fin ya pasó queda vencida
  update public.suscripciones set estado = 'vencida'
    where user_id = p_user and estado = 'activa' and fin is not null and fin < now();

  select * into v_sub from public.suscripciones
    where user_id = p_user and estado = 'activa';
  select * into v_plan from public.planes
    where id = coalesce(v_sub.plan_id, 'gratis');

  v_ciclo := case v_plan.periodo_limite
               when 'total' then 'total'
               else to_char(now() at time zone 'America/Bogota', 'YYYY-MM') end;

  -- Regenerar un informe ya cobrado en este ciclo no gasta otro cupo
  if exists (select 1 from public.consumo_informes
             where informe_id = p_informe and ciclo = v_ciclo) then
    return jsonb_build_object('permitido', true, 'plan', v_plan.id, 'cobrado', false, 'ciclo', v_ciclo);
  end if;

  if v_plan.id = 'gratis' then
    -- La prueba gratis se cuenta por cédula (sobrevive a borrar la cuenta)
    select cedula into v_ced from public.profiles where id = p_user;
    if v_ced is null then
      return jsonb_build_object('permitido', false, 'motivo', 'sin_cedula', 'plan', 'gratis',
        'usados', 0, 'limite', v_plan.informes_limite, 'ciclo', v_ciclo);
    end if;
    perform pg_advisory_xact_lock(hashtext('prueba:' || v_ced));
    v_usados := public.usados_prueba(p_user);
    if v_usados >= v_plan.informes_limite then
      return jsonb_build_object('permitido', false, 'motivo', 'limite_alcanzado',
        'plan', v_plan.id, 'usados', v_usados, 'limite', v_plan.informes_limite, 'ciclo', v_ciclo);
    end if;
    insert into public.pruebas_gratis (cedula_hash, usados) values (public.hash_cedula(v_ced), v_usados + 1)
      on conflict (cedula_hash) do update set usados = excluded.usados, actualizado = now();
  elsif v_plan.informes_limite is not null then
    select count(*) into v_usados from public.consumo_informes
      where user_id = p_user and ciclo = v_ciclo and plan_id = v_plan.id;
    if v_usados >= v_plan.informes_limite then
      return jsonb_build_object('permitido', false, 'motivo', 'limite_alcanzado',
        'plan', v_plan.id, 'usados', v_usados, 'limite', v_plan.informes_limite, 'ciclo', v_ciclo);
    end if;
  end if;

  insert into public.consumo_informes (user_id, informe_id, plan_id, ciclo)
    values (p_user, p_informe, v_plan.id, v_ciclo);
  return jsonb_build_object('permitido', true, 'plan', v_plan.id, 'cobrado', true, 'ciclo', v_ciclo);
end; $$;

-- Si la generación falla, el backend devuelve el cupo (también el de la prueba por cédula)
create or replace function public.devolver_informe(p_user uuid, p_informe uuid, p_ciclo text)
returns void language plpgsql security definer set search_path = public as $$
declare
  v_plan text;
  v_ced text;
begin
  delete from public.consumo_informes
    where user_id = p_user and informe_id = p_informe and ciclo = p_ciclo
    returning plan_id into v_plan;
  if v_plan = 'gratis' then
    select cedula into v_ced from public.profiles where id = p_user;
    if v_ced is not null then
      update public.pruebas_gratis set usados = greatest(usados - 1, 0), actualizado = now()
        where cedula_hash = public.hash_cedula(v_ced);
    end if;
  end if;
end; $$;
revoke all on function public.devolver_informe(uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.devolver_informe(uuid, uuid, text) to service_role;

revoke all on function public.consumir_informe(uuid, uuid) from public, anon, authenticated;
grant execute on function public.consumir_informe(uuid, uuid) to service_role;

-- ---------------------------------------------------------------------
-- Estado del plan: plan vigente, usados, restantes y vencimiento.
-- ---------------------------------------------------------------------
create or replace function public.estado_suscripcion(p_user uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_sub public.suscripciones;
  v_plan public.planes;
  v_ciclo text;
  v_usados int;
begin
  if public.es_sin_limite(p_user) then
    return jsonb_build_object('plan', 'pruebas', 'plan_nombre', 'Pruebas', 'precio_cop', 0,
      'periodo_limite', 'mensual', 'limite', null, 'usados', 0, 'restantes', null, 'ciclo', 'pruebas',
      'inicio', null, 'fin', null, 'sin_limite', true);
  end if;

  update public.suscripciones set estado = 'vencida'
    where user_id = p_user and estado = 'activa' and fin is not null and fin < now();

  select * into v_sub from public.suscripciones
    where user_id = p_user and estado = 'activa';
  select * into v_plan from public.planes
    where id = coalesce(v_sub.plan_id, 'gratis');

  v_ciclo := case v_plan.periodo_limite
               when 'total' then 'total'
               else to_char(now() at time zone 'America/Bogota', 'YYYY-MM') end;

  if v_plan.id = 'gratis' then
    v_usados := public.usados_prueba(p_user);
  else
    select count(*) into v_usados from public.consumo_informes
      where user_id = p_user and ciclo = v_ciclo and plan_id = v_plan.id;
  end if;

  return jsonb_build_object(
    'plan', v_plan.id,
    'plan_nombre', v_plan.nombre,
    'precio_cop', v_plan.precio_cop,
    'periodo_limite', v_plan.periodo_limite,
    'limite', v_plan.informes_limite,
    'usados', v_usados,
    'restantes', case when v_plan.informes_limite is null then null
                      else greatest(v_plan.informes_limite - v_usados, 0) end,
    'ciclo', v_ciclo,
    'inicio', v_sub.inicio,
    'fin', v_sub.fin);
end; $$;

revoke all on function public.estado_suscripcion(uuid) from public, anon, authenticated;
grant execute on function public.estado_suscripcion(uuid) to service_role;

-- ---------------------------------------------------------------------
-- Aplica el resultado de un pago de forma atómica e idempotente.
-- p_estado: 'aprobado' | 'rechazado' | 'anulado' | 'error'
-- p_monto_centavos: monto informado por la pasarela, en centavos.
-- ---------------------------------------------------------------------
create or replace function public.procesar_pago(
  p_referencia text, p_estado text, p_id_transaccion text,
  p_monto_centavos bigint, p_evento jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_pago public.pagos;
  v_plan public.planes;
begin
  select * into v_pago from public.pagos where referencia = p_referencia for update;
  if not found then
    return jsonb_build_object('ok', false, 'motivo', 'referencia_desconocida');
  end if;
  if v_pago.monto_cop::bigint * 100 <> p_monto_centavos then
    return jsonb_build_object('ok', false, 'motivo', 'monto_no_coincide');
  end if;
  -- Ya aprobado: el mismo evento repetido no duplica nada
  if v_pago.estado = 'aprobado' then
    return jsonb_build_object('ok', true, 'estado', 'aprobado', 'duplicado', true);
  end if;

  if p_estado <> 'aprobado' then
    update public.pagos
       set estado = p_estado,
           id_transaccion = coalesce(p_id_transaccion, id_transaccion),
           evento_json = p_evento
     where id = v_pago.id;
    return jsonb_build_object('ok', true, 'estado', p_estado);
  end if;

  perform pg_advisory_xact_lock(hashtext(v_pago.user_id::text));
  select * into v_plan from public.planes where id = v_pago.plan_id;

  update public.pagos
     set estado = 'aprobado', id_transaccion = p_id_transaccion, evento_json = p_evento
   where id = v_pago.id;
  update public.suscripciones set estado = 'cancelada'
   where user_id = v_pago.user_id and estado = 'activa';
  insert into public.suscripciones (user_id, plan_id, inicio, fin)
    values (v_pago.user_id, v_pago.plan_id, now(),
            now() + make_interval(days => coalesce(v_plan.dias_vigencia, 30)));
  return jsonb_build_object('ok', true, 'estado', 'aprobado', 'activado', true);
end; $$;

revoke all on function public.procesar_pago(text, text, text, bigint, jsonb) from public, anon, authenticated;
grant execute on function public.procesar_pago(text, text, text, bigint, jsonb) to service_role;

-- =====================================================================
-- Seguridad por filas (RLS)
-- =====================================================================
alter table public.profiles enable row level security;
alter table public.contratos enable row level security;
alter table public.obligaciones enable row level security;
alter table public.plantillas_informe enable row level security;
alter table public.informes enable row level security;
alter table public.actividades enable row level security;
alter table public.evidencias enable row level security;
alter table public.ia_logs enable row level security;
alter table public.planes enable row level security;
alter table public.suscripciones enable row level security;
alter table public.pagos enable row level security;
alter table public.consumo_informes enable row level security;

drop policy if exists "perfil propio" on public.profiles;
create policy "perfil propio" on public.profiles
  for all using (id = auth.uid()) with check (id = auth.uid());

-- El usuario solo puede cambiar su nombre y su cédula (nunca su rol).
revoke insert, update, delete on public.profiles from anon, authenticated;
grant update (nombre_completo) on public.profiles to authenticated;
revoke update (cedula) on public.profiles from authenticated;  -- la cédula solo la fija el backend

drop policy if exists "contratos propios" on public.contratos;
create policy "contratos propios" on public.contratos
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "obligaciones del contrato propio" on public.obligaciones;
create policy "obligaciones del contrato propio" on public.obligaciones
  for all using (exists (select 1 from public.contratos c
    where c.id = contrato_id and c.user_id = auth.uid()))
  with check (exists (select 1 from public.contratos c
    where c.id = contrato_id and c.user_id = auth.uid()));

drop policy if exists "plantillas: ver globales y propias" on public.plantillas_informe;
create policy "plantillas: ver globales y propias" on public.plantillas_informe
  for select using (alcance = 'global' or user_id = auth.uid());
drop policy if exists "plantillas: gestionar propias" on public.plantillas_informe;
create policy "plantillas: gestionar propias" on public.plantillas_informe
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Además de ser del usuario, el informe debe colgar de un contrato suyo,
-- y la actividad de un informe suyo (evita mezclar filas con las de otro).
drop policy if exists "informes propios" on public.informes;
create policy "informes propios" on public.informes
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid() and exists (select 1 from public.contratos c
    where c.id = contrato_id and c.user_id = auth.uid()));

drop policy if exists "actividades propias" on public.actividades;
create policy "actividades propias" on public.actividades
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid() and exists (select 1 from public.informes i
    where i.id = informe_id and i.user_id = auth.uid()));

drop policy if exists "evidencias propias" on public.evidencias;
create policy "evidencias propias" on public.evidencias
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid() and exists (select 1 from public.actividades a
    where a.id = actividad_id and a.user_id = auth.uid()));

-- ia_logs: sin políticas para usuarios; solo el backend (service role) escribe.

-- Planes, suscripciones, pagos y consumo: el usuario solo lee.
drop policy if exists "planes visibles" on public.planes;
create policy "planes visibles" on public.planes
  for select to authenticated using (true);
drop policy if exists "suscripciones propias (lectura)" on public.suscripciones;
create policy "suscripciones propias (lectura)" on public.suscripciones
  for select using (user_id = auth.uid());
drop policy if exists "pagos propios (lectura)" on public.pagos;
create policy "pagos propios (lectura)" on public.pagos
  for select using (user_id = auth.uid());
drop policy if exists "consumo propio (lectura)" on public.consumo_informes;
create policy "consumo propio (lectura)" on public.consumo_informes
  for select using (user_id = auth.uid());

-- Solo el backend escribe. Con la llave pública y su token, el usuario puede LEER sus filas, pero no crear ni
-- cambiar contratos, obligaciones, informes, actividades ni evidencias saltándose las validaciones del backend
-- (cédula de la minuta, cupo, archivos permitidos). Las políticas "for all" de arriba quedan solo para leer.
revoke insert, update, delete on public.contratos, public.obligaciones, public.plantillas_informe,
  public.informes, public.actividades, public.evidencias from anon, authenticated;
revoke all on public.ia_logs, public.cuentas_sin_limite, public.pruebas_gratis, public.lecturas_minuta
  from anon, authenticated;

-- =====================================================================
-- Límite de solicitudes a la IA por usuario (compartido entre todos los procesos del servidor y que
-- sobrevive a los reinicios). Protege el saldo de OpenRouter.
-- =====================================================================
create table if not exists public.solicitudes_ia (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  accion text not null,
  created_at timestamptz not null default now()
);
create index if not exists solicitudes_ia_usuario on public.solicitudes_ia(user_id, accion, created_at);
alter table public.solicitudes_ia enable row level security;
revoke all on public.solicitudes_ia from anon, authenticated;

create or replace function public.registrar_solicitud(p_user uuid, p_accion text, p_maximo int, p_ventana_s int)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_desde timestamptz := now() - make_interval(secs => p_ventana_s);
  v_n int;
  v_primera timestamptz;
begin
  perform pg_advisory_xact_lock(hashtext('solicitud:' || p_user::text || ':' || p_accion));
  delete from public.solicitudes_ia where user_id = p_user and accion = p_accion and created_at <= v_desde;
  select count(*), min(created_at) into v_n, v_primera
    from public.solicitudes_ia where user_id = p_user and accion = p_accion;
  if v_n >= p_maximo then
    return jsonb_build_object('ok', false, 'espera_s',
      greatest(1, ceil(extract(epoch from (v_primera + make_interval(secs => p_ventana_s) - now())))::int));
  end if;
  insert into public.solicitudes_ia (user_id, accion) values (p_user, p_accion);
  return jsonb_build_object('ok', true);
end $$;
revoke all on function public.registrar_solicitud(uuid, text, int, int) from public, anon, authenticated;
grant execute on function public.registrar_solicitud(uuid, text, int, int) to service_role;

-- =====================================================================
-- Storage: buckets privados (máximo 20 MB por archivo)
-- Cada usuario solo lee y escribe en la carpeta {su user_id}/...
-- =====================================================================
insert into storage.buckets (id, name, public, file_size_limit) values
  ('minutas',    'minutas',    false, 20971520),
  ('plantillas', 'plantillas', false, 20971520),
  ('informes',   'informes',   false, 20971520),
  ('evidencias', 'evidencias', false, 20971520)
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit;

drop policy if exists "archivos propios: leer" on storage.objects;
create policy "archivos propios: leer" on storage.objects
  for select to authenticated
  using (bucket_id in ('minutas','plantillas','informes','evidencias')
         and (storage.foldername(name))[1] = auth.uid()::text);

-- Subir, cambiar y borrar archivos solo lo hace el backend (valida tipo y tamaño). Sin estas políticas nadie
-- puede llenar el almacenamiento subiendo archivos directo con la llave pública.
drop policy if exists "archivos propios: subir" on storage.objects;
drop policy if exists "archivos propios: actualizar" on storage.objects;
drop policy if exists "archivos propios: borrar" on storage.objects;
