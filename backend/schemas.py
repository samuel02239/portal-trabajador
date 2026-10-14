"""Modelos pydantic: respuestas de la IA y cuerpos de la API."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

TipoContratacion = Literal["prestacion_servicios", "practica_formativa", "otro"]
TipoObligacion = Literal["especifica", "general"]


# ----------------------------------------------------------------- normalizadores
def a_fecha(v):
    """Acepta 'YYYY-MM-DD', 'DD/MM/YYYY', fechas o vacío."""
    if v in (None, "", "null"):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def a_numero(v):
    """Acepta 7500000, '7,500,000.00', '$7.500.000' o vacío."""
    if v in (None, "", "null"):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s:
        return None
    if "," in s and "." in s:
        # El último separador es el decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3):
        s = s.replace(".", "")
    elif s.count(",") > 1 or (s.count(",") == 1 and len(s.split(",")[1]) == 3):
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def a_texto(v):
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None


# ------------------------------------------------------------------- IA: minuta
class ContratoIA(BaseModel):
    numero: Optional[str] = None
    entidad: Optional[str] = None
    tipo_contratacion: TipoContratacion = "prestacion_servicios"
    proyecto: Optional[str] = None
    objeto: Optional[str] = None
    dependencia: Optional[str] = None
    fecha_contrato: Optional[date] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    plazo_texto: Optional[str] = None
    valor_total: Optional[float] = None
    forma_pago: Optional[str] = None

    @field_validator("numero", "entidad", "proyecto", "objeto", "dependencia", "plazo_texto", "forma_pago",
                     mode="before")
    @classmethod
    def _txt(cls, v):
        return a_texto(v)

    @field_validator("fecha_contrato", "fecha_inicio", "fecha_fin", mode="before")
    @classmethod
    def _fechas(cls, v):
        return a_fecha(v)

    @field_validator("valor_total", mode="before")
    @classmethod
    def _valor(cls, v):
        return a_numero(v)

    @field_validator("tipo_contratacion", mode="before")
    @classmethod
    def _tipo(cls, v):
        s = (str(v or "").lower().strip().replace(" ", "_"))
        if "practica" in s or "práctica" in s:
            return "practica_formativa"
        if "prestacion" in s or "prestación" in s or not s:
            return "prestacion_servicios"
        return s if s in ("prestacion_servicios", "practica_formativa") else "otro"


class PersonaIA(BaseModel):
    nombre: Optional[str] = None
    cedula: Optional[str] = None

    @field_validator("nombre", mode="before")
    @classmethod
    def _n(cls, v):
        return a_texto(v)

    @field_validator("cedula", mode="before")
    @classmethod
    def _c(cls, v):
        s = a_texto(v)
        return re.sub(r"[^\dA-Za-z\-]", "", s) if s else None


class SupervisorIA(BaseModel):
    nombre: Optional[str] = None
    cargo: Optional[str] = None

    @field_validator("nombre", "cargo", mode="before")
    @classmethod
    def _t(cls, v):
        return a_texto(v)


class ObligacionIA(BaseModel):
    numero: int = Field(ge=1, le=200)
    tipo: TipoObligacion = "especifica"
    texto: str = ""  # vacío cuando el texto exacto ya se sacó del documento con la numeración
    palabras_clave: list[str] = Field(default_factory=list)

    @field_validator("tipo", mode="before")
    @classmethod
    def _tipo(cls, v):
        s = str(v or "").lower()
        return "general" if s.startswith("gen") else "especifica"

    @field_validator("texto", mode="before")
    @classmethod
    def _texto(cls, v):
        return a_texto(v) or ""

    @field_validator("palabras_clave", mode="before")
    @classmethod
    def _claves(cls, v):
        if not v:
            return []
        if isinstance(v, str):
            v = v.split(",")
        return [a_texto(x) for x in v if a_texto(x)][:12]


class MinutaIA(BaseModel):
    contrato: ContratoIA = Field(default_factory=ContratoIA)
    contratista: PersonaIA = Field(default_factory=PersonaIA)
    supervisor: SupervisorIA = Field(default_factory=SupervisorIA)
    obligaciones: list[ObligacionIA] = Field(default_factory=list)

    @model_validator(mode="after")
    def _con_obligaciones(self):
        if not any(o.tipo == "especifica" for o in self.obligaciones):
            raise ValueError("no se encontraron obligaciones específicas")
        return self


# -------------------------------------------------------------- IA: clasificación
class AsignacionIA(BaseModel):
    obligacion_numero: int = Field(ge=1)
    confianza: float = Field(ge=0, le=1)
    redaccion: str = Field(min_length=3)
    justificacion: str = ""

    @field_validator("confianza", mode="before")
    @classmethod
    def _conf(cls, v):
        n = a_numero(v)
        if n is None:
            return 0.0
        return n / 100 if n > 1 else n

    @field_validator("redaccion", "justificacion", mode="before")
    @classmethod
    def _t(cls, v):
        return a_texto(v) or ""


class ClasificacionIA(BaseModel):
    asignaciones: list[AsignacionIA] = Field(default_factory=list)
    sin_coincidencia: bool = False
    pregunta_aclaracion: Optional[str] = None

    @field_validator("pregunta_aclaracion", mode="before")
    @classmethod
    def _p(cls, v):
        return a_texto(v)

    @model_validator(mode="after")
    def _coherente(self):
        if not self.asignaciones and not self.sin_coincidencia:
            raise ValueError("debe haber al menos una asignación o sin_coincidencia = true")
        self.asignaciones.sort(key=lambda a: a.confianza, reverse=True)
        return self


# ------------------------------------------------------------------ API: entradas
class ContratoDatos(BaseModel):
    numero_contrato: Optional[str] = None
    entidad: Optional[str] = None
    tipo_contratacion: TipoContratacion = "prestacion_servicios"
    proyecto: Optional[str] = None
    objeto: Optional[str] = None
    dependencia: Optional[str] = None
    supervisor_nombre: Optional[str] = None
    supervisor_cargo: Optional[str] = None
    fecha_contrato: Optional[date] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    plazo_texto: Optional[str] = None
    valor_total: Optional[float] = None
    forma_pago: Optional[str] = None

    @field_validator("numero_contrato", "entidad", "proyecto", "objeto", "dependencia", "supervisor_nombre",
                     "supervisor_cargo", "plazo_texto", "forma_pago", mode="before")
    @classmethod
    def _txt(cls, v):
        return a_texto(v)

    @model_validator(mode="after")
    def _fechas(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("la fecha de terminación es anterior a la fecha de inicio")
        return self


class ObligacionEntrada(BaseModel):
    id: Optional[str] = None
    numero: int = Field(ge=1, le=200)
    tipo: TipoObligacion = "especifica"
    texto: str = Field(min_length=3, max_length=4000)
    palabras_clave: list[str] = Field(default_factory=list)


class ContratoGuardar(BaseModel):
    """lectura_id: el id que devolvió /contratos/minuta (el texto de la minuta se queda en el servidor)."""
    lectura_id: str = Field(min_length=10, max_length=64)
    contrato: ContratoDatos
    contratista: PersonaIA = Field(default_factory=PersonaIA)
    obligaciones: list[ObligacionEntrada] = Field(min_length=1)


class ContratoEditar(BaseModel):
    contrato: ContratoDatos
    contratista: PersonaIA = Field(default_factory=PersonaIA)
    obligaciones: list[ObligacionEntrada] = Field(min_length=1)


class ClasificarEntrada(BaseModel):
    texto: str = Field(min_length=3, max_length=2000)
    fecha: Optional[date] = None


class ActividadCrear(BaseModel):
    fecha: date
    texto_original: str = Field(min_length=1, max_length=4000)
    texto_redactado: Optional[str] = Field(default=None, max_length=6000)
    obligacion_id: Optional[str] = None
    confianza: Optional[float] = Field(default=None, ge=0, le=1)
    estado: Literal["propuesta", "confirmada", "sin_obligacion"] = "confirmada"
    modelo_usado: Optional[str] = None


class ActividadEditar(BaseModel):
    """Solo se cambian los campos enviados. obligacion_id = null la deja sin obligación."""
    texto_redactado: Optional[str] = Field(default=None, max_length=6000)
    obligacion_id: Optional[str] = None
    fecha: Optional[date] = None


class EvidenciaEditar(BaseModel):
    """descripcion: texto nuevo del anexo. regenerar = True: la IA la vuelve a escribir según la actividad."""
    descripcion: Optional[str] = Field(default=None, max_length=300)
    regenerar: bool = False


class GenerarEntrada(BaseModel):
    tipo: Literal["parcial", "final"] = "parcial"
    fecha_elaboracion: Optional[date] = None


class CheckoutEntrada(BaseModel):
    plan_id: Literal["normal", "pro"]


class ConfirmarPlantilla(BaseModel):
    mapa_campos: Optional[dict] = None
