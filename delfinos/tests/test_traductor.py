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
