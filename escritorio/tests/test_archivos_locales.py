"""Copia local de las evidencias en la carpeta del mes."""
from datetime import date


def test_guarda_copia_sin_pisar(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("PORTAL_CARPETA_EVIDENCIAS", str(tmp_path / "Evidencias"))
    from app.servicios import archivos_locales

    origen = tmp_path / "Foto del mantenimiento (1).JPG"
    origen.write_bytes(b"\xff\xd8\xff" + b"0" * 50)
    c1 = archivos_locales.guardar_copia(origen, date(2026, 10, 8))
    c2 = archivos_locales.guardar_copia(origen, date(2026, 10, 8))
    assert c1.parent == tmp_path / "Evidencias" / "2026-10"
    assert c1.name == "2026-10-08_Foto_del_mantenimiento_1_.JPG"
    assert c2 != c1 and c2.exists() and c1.read_bytes() == origen.read_bytes()
    assert archivos_locales.es_imagen(c1)
    assert archivos_locales.guardar_copia(c1, date(2026, 10, 8)) == c1  # ya está en la carpeta: no se duplica
