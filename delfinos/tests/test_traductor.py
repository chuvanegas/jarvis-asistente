import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "herramientas"))
import delfin_traductor as dt  # noqa: E402


def test_traduce_copia_sin_tocar_original(tmp_path, capsys):
    app = tmp_path / "mi_app"
    app.mkdir()
    (app / "application.fam").write_text('App(\n    appid="mi_app",\n    name="Settings",\n)\n')
    src = '#include "Read.h"\nsubmenu_add_item(m, "Read", 0);\nwidget(w, "Apply card to\\nFlipper\'s back");\nFURI_LOG_I("mi_tag", "x");\nadd("Beninca");\nadd("Jump Height");\n'
    (app / "app.c").write_text(src)

    assert dt.main([str(app)]) == 0
    out = capsys.readouterr().out
    es = (tmp_path / "mi_app_es" / "app.c").read_text()
    assert (app / "app.c").read_text() == src  # original intacto
    assert '"Leer"' in es and '#include "Read.h"' in es
    assert "Acerca la tarjeta\\na la parte trasera" in es
    assert 'name="Ajustes"' in (tmp_path / "mi_app_es" / "application.fam").read_text()
    assert 'appid="mi_app"' in (tmp_path / "mi_app_es" / "application.fam").read_text()
    assert "'Jump Height'" in out and "Beninca" not in out and "mi_tag" not in out


def test_no_rompe_claves_de_archivo_ni_comparaciones():
    terminos = {"Frequency": "Frecuencia", "Read": "Leer", "Infrared": "Infrarrojo"}
    src = (
        'flipper_format_write_uint32(ff, "Frequency", &f, 1);\n'
        'flipper_format_read_string(\n    ff,\n    "Frequency",\n    s);\n'
        'if(strcmp(name, "Read") == 0) {}\n'
        'loader_start(loader, "Infrared", NULL, NULL);\n'
        '#define SUBGHZ_KEY_FREQ "Frequency"\n'
        'FURI_LOG_I(TAG, "Read");\n'
        'submenu_add_item(m, "Read", 0, cb, app);\n'
        'widget_add_string_element(w, 0, 0, AlignLeft, AlignTop, FontPrimary, "Frequency");\n'
    )
    out, n = dt.traducir_texto(src, terminos, set(), {}, ".c")
    lineas = out.split("\n")
    assert '"Frequency"' in lineas[0] and '"Frequency"' in lineas[3]
    assert '"Read"' in lineas[5] and '"Infrared"' in lineas[6] and '"Frequency"' in lineas[7]
    assert '"Read"' in lineas[8]
    assert '"Leer"' in lineas[9] and '"Frecuencia"' in lineas[10]
    assert n == 2


def test_fam_sin_nombre_y_en_sitio(tmp_path):
    app = tmp_path / "infrared"
    app.mkdir()
    (app / "application.fam").write_text('App(\n    appid="infrared",\n    name="Settings",\n)\n')
    (app / "infrared_cli.c").write_text('printf("Read");\nsubmenu_add_item(m, "Read", 0, cb, app);\n')
    (app / "scene.c").write_text('submenu_add_item(m, "Read", 0, cb, app);\n')
    assert dt.main([str(app), "--en-sitio", "--sin-nombre-fam"]) == 0
    assert 'name="Settings"' in (app / "application.fam").read_text()
    assert '"Read"' in (app / "infrared_cli.c").read_text()  # archivos CLI no se tocan
    assert '"Leer"' in (app / "scene.c").read_text()


def test_protege_nombres_de_apps(tmp_path):
    raiz = tmp_path / "fw"
    (raiz / "apps" / "clock").mkdir(parents=True)
    (raiz / "apps" / "clock" / "application.fam").write_text('App(appid="clock", name="Clock")\n')
    c = raiz / "apps" / "keybinds.c"
    c.write_text('furi_string_set(keybind, "Clock");\nsubmenu_add_item(m, "Read", 0, cb, app);\n'
                 'const char* const easy_mode_button_names[] = {"Power", "Down"};\n'
                 'const X d = {.app_name = "Storage", .x = 1};\n')
    assert dt.main([str(raiz / "apps"), "--en-sitio", "--sin-nombre-fam", "--proteger-apps", str(raiz)]) == 0
    t = c.read_text()
    assert '"Clock"' in t and '"Leer"' in t and '"Down"' in t and '"Storage"' in t


def test_conserva_finales_de_linea_crlf(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "a.c").write_bytes(b'x();\r\nsubmenu_add_item(m, "Read", 0, cb, app);\r\n')
    dt.main([str(app), "--en-sitio"])
    assert (app / "a.c").read_bytes() == b'x();\r\nsubmenu_add_item(m, "Leer", 0, cb, app);\r\n'


def test_texto_comparado_no_se_traduce_en_ningun_lado(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "a.c").write_text('const char* d = "Settings";\nsubmenu_add_item(m, "Settings", 0, cb, app);\n')
    (app / "b.c").write_text('if(furi_string_equal(k, "Settings")) {}\nsubmenu_add_item(m, "Read", 0, cb, app);\n')
    dt.main([str(app), "--en-sitio"])
    assert '"Ajustes"' not in (app / "a.c").read_text()
    assert '"Leer"' in (app / "b.c").read_text()
