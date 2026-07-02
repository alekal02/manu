import json
import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
FRONT_DIR = os.path.join(ROOT_DIR, "front")
TEMPLATES_DIR = os.path.join(FRONT_DIR, "templates")
STATIC_DIR = os.path.join(FRONT_DIR, "static")

if not os.path.isdir(TEMPLATES_DIR):
    raise RuntimeError(
        f"Pasta de templates não encontrada: {TEMPLATES_DIR}\n"
        "Execute o projeto a partir de C:\\manu com: python app.py"
    )

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR,
)
app.secret_key = os.environ.get("SECRET_KEY", "manu-dev-key-altere-em-producao")

DATA_FILE = os.path.join(BASE_DIR, "data", "ativos.json")
USERS_FILE = os.path.join(BASE_DIR, "data", "usuarios.json")


def garantir_usuarios():
    if os.path.exists(USERS_FILE):
        return
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    usuarios = [
        {
            "usuario": "gerente",
            "senha_hash": generate_password_hash("1234"),
            "nome": "Gerente",
            "nivel": "gerente",
            "senha_alterada": False,
        },
        {
            "usuario": "fiscal",
            "senha_hash": generate_password_hash("1234"),
            "nome": "Fiscal",
            "nivel": "fiscal",
            "senha_alterada": False,
        },
    ]
    salvar_usuarios(usuarios)


def salvar_usuarios(usuarios):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=2)


def migrar_usuarios():
    garantir_usuarios()
    usuarios = carregar_usuarios()
    alterou = False
    for u in usuarios:
        if "senha_alterada" not in u:
            u["senha_hash"] = generate_password_hash("1234")
            u["senha_alterada"] = False
            alterou = True
    if alterou:
        salvar_usuarios(usuarios)


def carregar_usuarios():
    garantir_usuarios()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def autenticar(usuario, senha):
    for u in carregar_usuarios():
        if u["usuario"] == usuario and check_password_hash(u["senha_hash"], senha):
            return u
    return None


def usuario_logado():
    if "usuario" not in session:
        return None
    for u in carregar_usuarios():
        if u["usuario"] == session["usuario"]:
            return u
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not usuario_logado():
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)

    return decorated


def fiscal_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = usuario_logado()
        if not user:
            return redirect(url_for("login", next=request.url))
        if user["nivel"] != "fiscal":
            flash("Acesso restrito ao perfil Fiscal.", "error")
            return redirect(url_for("verificacao"))
        return f(*args, **kwargs)

    return decorated


def carregar_ativos():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_ativos(ativos):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(ativos, f, ensure_ascii=False, indent=2)


def proximo_id(ativos):
    if not ativos:
        return 1
    return max(a["id"] for a in ativos) + 1


def formatar_data(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_str


app.jinja_env.filters["formatar_data"] = formatar_data


@app.context_processor
def inject_user():
    user = usuario_logado()
    return {
        "current_user": user,
        "is_fiscal": user and user["nivel"] == "fiscal",
        "is_gerente": user and user["nivel"] == "gerente",
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if usuario_logado():
        return redirect(url_for("verificacao"))

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        user = autenticar(usuario, senha)
        if user:
            session["usuario"] = user["usuario"]
            session["nivel"] = user["nivel"]
            session["nome"] = user["nome"]
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("verificacao"))
        flash("Usuário ou senha inválidos.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for("login"))


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    user = usuario_logado()

    if request.method == "POST":
        senha_atual = request.form.get("senha_atual", "")
        nova_senha = request.form.get("nova_senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        if not check_password_hash(user["senha_hash"], senha_atual):
            flash("Senha atual incorreta.", "error")
            return render_template("perfil.html", user=user)

        if len(nova_senha) < 4:
            flash("A nova senha deve ter pelo menos 4 caracteres.", "error")
            return render_template("perfil.html", user=user)

        if nova_senha != confirmar:
            flash("As senhas não coincidem.", "error")
            return render_template("perfil.html", user=user)

        usuarios = carregar_usuarios()
        for u in usuarios:
            if u["usuario"] == user["usuario"]:
                u["senha_hash"] = generate_password_hash(nova_senha)
                u["senha_alterada"] = True
                break
        salvar_usuarios(usuarios)
        flash("Senha alterada com sucesso!", "success")
        return redirect(url_for("perfil"))

    return render_template("perfil.html", user=user)


@app.route("/")
@login_required
def verificacao():
    ativos = carregar_ativos()
    em_manutencao = [a for a in ativos if a.get("em_manutencao")]
    na_base = [a for a in em_manutencao if a.get("local") == "base"]
    em_terceiros = [a for a in em_manutencao if a.get("local") == "terceiros"]
    return render_template(
        "verificacao.html",
        ativos=ativos,
        em_manutencao=em_manutencao,
        na_base=na_base,
        em_terceiros=em_terceiros,
        total=len(ativos),
        total_manutencao=len(em_manutencao),
    )


@app.route("/edicao")
@fiscal_required
def edicao():
    ativos = carregar_ativos()
    return render_template("edicao.html", ativos=ativos)


@app.route("/edicao/salvar/<int:ativo_id>", methods=["POST"])
@fiscal_required
def salvar_ativo(ativo_id):
    ativos = carregar_ativos()
    ativo = next((a for a in ativos if a["id"] == ativo_id), None)
    if not ativo:
        return redirect(url_for("edicao"))

    ativo["em_manutencao"] = request.form.get("em_manutencao") == "sim"
    ativo["local"] = request.form.get("local", "base")
    ativo["ordem_servico"] = request.form.get("ordem_servico", "").strip()
    ativo["observacoes"] = request.form.get("observacoes", "").strip()
    ativo["atualizado_em"] = datetime.now().isoformat(timespec="seconds")

    salvar_ativos(ativos)
    return redirect(url_for("edicao", salvo=ativo_id))


@app.route("/edicao/novo", methods=["POST"])
@fiscal_required
def novo_ativo():
    ativos = carregar_ativos()
    nome = request.form.get("nome", "").strip()
    codigo = request.form.get("codigo", "").strip()

    if not nome or not codigo:
        return redirect(url_for("edicao", erro="preencha_nome_codigo"))

    novo = {
        "id": proximo_id(ativos),
        "nome": nome,
        "codigo": codigo,
        "local": request.form.get("local", "base"),
        "em_manutencao": request.form.get("em_manutencao") == "sim",
        "ordem_servico": request.form.get("ordem_servico", "").strip(),
        "observacoes": request.form.get("observacoes", "").strip(),
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
    }
    ativos.append(novo)
    salvar_ativos(ativos)
    return redirect(url_for("edicao", salvo=novo["id"]))


@app.route("/api/ativos")
@login_required
def api_ativos():
    return jsonify(carregar_ativos())


migrar_usuarios()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
