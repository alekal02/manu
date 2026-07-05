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
    send_file,
    session,
    url_for,
)
from io import BytesIO
from werkzeug.security import check_password_hash

from config import SECRET_KEY
from db import init_db
from pdf_reports import gerar_pdf_diario, gerar_pdf_mensal
from services import (
    ACAO_LABEL,
    LOCAIS,
    admin_alterar_senha_admin,
    admin_atualizar_base,
    admin_atualizar_usuario,
    admin_criar_usuario,
    admin_excluir_base,
    admin_resetar_senha,
    admin_toggle_usuario,
    autenticar,
    autenticar_admin,
    contar_bases,
    criar_ativo,
    excluir_ativo,
    importar_ativos_csv,
    listar_ativos,
    listar_bases,
    listar_bases_admin,
    listar_todos_usuarios,
    normalizar_local,
    obter_admin,
    obter_base,
    obter_ativo,
    obter_usuario,
    obter_usuario_por_id,
    relatorio_diario,
    relatorio_mensal,
    salvar_ativo,
    seed_bases,
    atualizar_senha,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
FRONT_DIR = os.path.join(ROOT_DIR, "front")
TEMPLATES_DIR = os.path.join(FRONT_DIR, "templates")
STATIC_DIR = os.path.join(FRONT_DIR, "static")

if not os.path.isdir(TEMPLATES_DIR):
    raise RuntimeError(
        f"Pasta de templates não encontrada: {TEMPLATES_DIR}\n"
        "Execute o projeto a partir de C:\\manu\\manu com: python app.py"
    )

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR,
)
app.secret_key = SECRET_KEY


def formatar_data(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_str


app.jinja_env.filters["formatar_data"] = formatar_data


@app.template_filter("acao_label")
def acao_label_filter(acao):
    return ACAO_LABEL.get(acao, acao.capitalize())


@app.template_filter("local_label")
def local_label_filter(local):
    return LOCAIS.get(local, local or "—")


@app.template_filter("formatar_data_curta")
def formatar_data_curta_filter(iso_str):
    if not iso_str:
        return "—"
    try:
        if len(iso_str) == 10:
            dt = datetime.strptime(iso_str, "%Y-%m-%d")
        else:
            dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_str


@app.template_filter("formatar_hora")
def formatar_hora_filter(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%H:%M")
    except ValueError:
        return iso_str


@app.template_filter("nome_mes")
def nome_mes_filter(mes):
    meses = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    try:
        return meses[int(mes)]
    except (ValueError, IndexError):
        return mes


def usuario_logado():
    if session.get("tipo") == "admin":
        return None
    if "usuario" not in session or "base_id" not in session:
        return None
    user = obter_usuario(session["base_id"], session["usuario"])
    if not user:
        return None
    user["base_nome"] = session.get("base_nome", "")
    user["base_codigo"] = session.get("base_codigo", "")
    return user


def admin_logado():
    if session.get("tipo") != "admin" or "admin_id" not in session:
        return None
    return obter_admin(session["admin_id"])


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


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not admin_logado():
            return redirect(url_for("admin_login", next=request.url))
        return f(*args, **kwargs)

    return decorated


def base_id_sessao():
    return session["base_id"]


def usuario_acao():
    user = usuario_logado()
    if not user:
        return None, None
    return user["usuario"], user["nome"]


@app.context_processor
def inject_user():
    user = usuario_logado()
    admin = admin_logado()
    return {
        "current_user": user,
        "current_admin": admin,
        "is_fiscal": user and user["nivel"] == "fiscal",
        "is_gerente": user and user["nivel"] == "gerente",
        "is_admin": admin is not None,
        "locais": LOCAIS,
    }


@app.before_request
def garantir_banco():
    if request.endpoint in ("static", None):
        return
    init_db()
    if request.endpoint == "login" and request.method == "GET" and contar_bases() == 0:
        seed_bases(20)


@app.route("/login", methods=["GET", "POST"])
def login():
    if admin_logado():
        return redirect(url_for("admin_usuarios"))
    if usuario_logado():
        return redirect(url_for("verificacao"))

    bases = listar_bases()

    if request.method == "POST":
        base_id = request.form.get("base_id", "").strip()
        usuario = request.form.get("usuario", "").strip().lower()
        senha = request.form.get("senha", "")

        if not base_id:
            flash("Selecione a filial.", "error")
            return render_template("login.html", bases=bases)

        user = autenticar(base_id, usuario, senha)
        if user:
            session.clear()
            session["base_id"] = user["base_id"]
            session["base_nome"] = user["base_nome"]
            session["base_codigo"] = user["base_codigo"]
            session["usuario"] = user["usuario"]
            session["nivel"] = user["nivel"]
            session["nome"] = user["nome"]
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("verificacao"))
        flash("Filial, usuário ou senha inválidos.", "error")

    return render_template("login.html", bases=bases)


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

        atualizar_senha(user["base_id"], user["usuario"], nova_senha)
        flash("Senha alterada com sucesso!", "success")
        return redirect(url_for("perfil"))

    return render_template("perfil.html", user=user)


@app.route("/")
@login_required
def verificacao():
    ativos = listar_ativos(base_id_sessao())
    em_manutencao = [a for a in ativos if a.get("em_manutencao")]
    operacionais = [a for a in ativos if not a.get("em_manutencao")]
    na_base = [a for a in ativos if a.get("local") == "base"]
    em_servico = [a for a in ativos if a.get("local") == "servico"]
    em_deslocamento = [a for a in ativos if a.get("local") == "deslocamento"]
    em_terceiros = [a for a in ativos if a.get("local") == "terceiros"]
    em_manutencao_na_base = [a for a in em_manutencao if a.get("local") == "base"]
    em_manutencao_terceiros = [a for a in em_manutencao if a.get("local") == "terceiros"]
    total = len(ativos)
    total_manutencao = len(em_manutencao)
    pct_operacional = round((len(operacionais) / total) * 100) if total else 0
    pct_manutencao = round((total_manutencao / total) * 100) if total else 0
    return render_template(
        "verificacao.html",
        ativos=ativos,
        operacionais=operacionais,
        em_manutencao=em_manutencao,
        na_base=na_base,
        em_servico=em_servico,
        em_deslocamento=em_deslocamento,
        em_terceiros=em_terceiros,
        em_manutencao_na_base=em_manutencao_na_base,
        em_manutencao_terceiros=em_manutencao_terceiros,
        total=total,
        total_manutencao=total_manutencao,
        total_operacional=len(operacionais),
        pct_operacional=pct_operacional,
        pct_manutencao=pct_manutencao,
    )


@app.route("/edicao")
@fiscal_required
def edicao():
    ativos = listar_ativos(base_id_sessao())
    return render_template("edicao.html", ativos=ativos)


@app.route("/edicao/salvar/<string:ativo_id>", methods=["POST"])
@fiscal_required
def salvar_ativo_route(ativo_id):
    ativo = obter_ativo(base_id_sessao(), ativo_id)
    if not ativo:
        return redirect(url_for("edicao"))

    nome = request.form.get("nome", "").strip()
    codigo = request.form.get("codigo", "").strip()
    if not nome or not codigo:
        flash("Nome e código são obrigatórios.", "error")
        return redirect(url_for("edicao", erro="preencha_nome_codigo"))

    try:
        salvar_ativo(
            base_id_sessao(),
            ativo_id,
            {
                "nome": nome,
                "codigo": codigo,
                "em_manutencao": request.form.get("em_manutencao") == "sim",
                "local": normalizar_local(request.form.get("local", "base")),
                "ordem_servico": request.form.get("ordem_servico", "").strip(),
                "observacoes": request.form.get("observacoes", "").strip(),
            },
            *usuario_acao(),
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("edicao"))

    return redirect(url_for("edicao", salvo=ativo_id))


@app.route("/edicao/excluir/<string:ativo_id>", methods=["POST"])
@fiscal_required
def excluir_ativo_route(ativo_id):
    ativo = obter_ativo(base_id_sessao(), ativo_id)
    if not ativo:
        flash("Ativo não encontrado.", "error")
        return redirect(url_for("edicao"))

    excluir_ativo(base_id_sessao(), ativo_id, *usuario_acao())
    flash(f"Ativo {ativo['codigo']} excluído com sucesso.", "success")
    return redirect(url_for("edicao"))


@app.route("/edicao/novo", methods=["POST"])
@fiscal_required
def novo_ativo():
    nome_ativo = request.form.get("nome", "").strip()
    codigo = request.form.get("codigo", "").strip()

    if not nome_ativo or not codigo:
        return redirect(url_for("edicao", erro="preencha_nome_codigo"))

    try:
        usr, usr_nome = usuario_acao()
        novo_id = criar_ativo(
            base_id_sessao(),
            {
                "nome": nome_ativo,
                "codigo": codigo,
                "local": normalizar_local(request.form.get("local", "base")),
                "em_manutencao": request.form.get("em_manutencao") == "sim",
                "ordem_servico": request.form.get("ordem_servico", "").strip(),
                "observacoes": request.form.get("observacoes", "").strip(),
            },
            usr,
            usr_nome,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("edicao"))

    return redirect(url_for("edicao", salvo=novo_id))


@app.route("/edicao/importar", methods=["POST"])
@fiscal_required
def importar_ativos():
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        flash("Selecione um arquivo CSV ou Excel.", "error")
        return redirect(url_for("edicao"))

    substituir = request.form.get("substituir") == "sim"
    try:
        usr, usr_nome = usuario_acao()
        resultado = importar_ativos_csv(
            base_id_sessao(),
            arquivo.read(),
            substituir=substituir,
            usuario=usr,
            usuario_nome=usr_nome,
            nome_arquivo=arquivo.filename,
        )
        flash(
            f"Importação concluída: {resultado['inseridos']} novos, "
            f"{resultado['atualizados']} atualizados "
            f"({resultado['total']} linhas no arquivo).",
            "success",
        )
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception:
        flash("Erro ao processar o arquivo. Verifique o formato CSV ou Excel.", "error")

    return redirect(url_for("edicao"))


@app.route("/edicao/modelo-importacao")
@fiscal_required
def download_modelo_importacao():
    caminho = os.path.join(BASE_DIR, "data", "modelo_importacao_ativos.xlsx")
    if not os.path.isfile(caminho):
        flash("Modelo de importação não encontrado.", "error")
        return redirect(url_for("edicao"))
    return send_file(
        caminho,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="modelo_importacao_ativos.xlsx",
    )


@app.route("/relatorios")
@login_required
def relatorios():
    aba = request.args.get("aba", "diario")
    data_ref = request.args.get("data", datetime.now().strftime("%Y-%m-%d"))

    ref_mes = request.args.get("ref_mes", "")
    if ref_mes and "-" in ref_mes:
        partes = ref_mes.split("-")
        ano, mes = int(partes[0]), int(partes[1])
    else:
        ano = int(request.args.get("ano", datetime.now().year))
        mes = int(request.args.get("mes", datetime.now().month))

    diario = relatorio_diario(base_id_sessao(), data_ref)
    mensal = relatorio_mensal(base_id_sessao(), ano, mes)

    return render_template(
        "relatorios.html",
        aba=aba,
        data_ref=data_ref,
        ref_mes=f"{ano:04d}-{mes:02d}",
        ano=ano,
        mes=mes,
        diario=diario,
        mensal=mensal,
    )


@app.route("/relatorios/pdf")
@login_required
def relatorio_pdf():
    user = usuario_logado()
    aba = request.args.get("aba", "diario")
    base_id = base_id_sessao()
    filial_codigo = user.get("base_codigo", "")
    filial_nome = user.get("base_nome", "")

    if aba == "mensal":
        ref_mes = request.args.get("ref_mes", "")
        if ref_mes and "-" in ref_mes:
            partes = ref_mes.split("-")
            ano, mes = int(partes[0]), int(partes[1])
        else:
            ano = int(request.args.get("ano", datetime.now().year))
            mes = int(request.args.get("mes", datetime.now().month))

        mensal = relatorio_mensal(base_id, ano, mes)
        pdf_bytes = gerar_pdf_mensal(filial_codigo, filial_nome, mensal)
        nome_arquivo = f"relatorio-mensal-{filial_codigo}-{ano:04d}-{mes:02d}.pdf"
    else:
        data_ref = request.args.get("data", datetime.now().strftime("%Y-%m-%d"))
        diario = relatorio_diario(base_id, data_ref)
        pdf_bytes = gerar_pdf_diario(filial_codigo, filial_nome, diario)
        nome_arquivo = f"relatorio-diario-{filial_codigo}-{data_ref}.pdf"

    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nome_arquivo,
    )


@app.route("/api/ativos")
@login_required
def api_ativos():
    return jsonify(listar_ativos(base_id_sessao()))


# --- Admin ---


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if admin_logado():
        return redirect(url_for("admin_usuarios"))

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip().lower()
        senha = request.form.get("senha", "")
        admin = autenticar_admin(usuario, senha)
        if admin:
            session.clear()
            session["tipo"] = "admin"
            session["admin_id"] = admin["id"]
            session["admin_usuario"] = admin["usuario"]
            session["admin_nome"] = admin["nome"]
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("admin_usuarios"))
        flash("Usuário ou senha de administrador inválidos.", "error")

    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Sessão administrativa encerrada.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@app.route("/admin/usuarios")
@admin_required
def admin_usuarios():
    filtro_base = request.args.get("base_id", "").strip()
    base_id = filtro_base if filtro_base else None
    usuarios = listar_todos_usuarios(base_id)
    bases = listar_bases(ativas_apenas=False)
    return render_template(
        "admin/usuarios.html",
        usuarios=usuarios,
        bases=bases,
        filtro_base=filtro_base,
    )


@app.route("/admin/filiais")
@admin_required
def admin_filiais():
    bases = listar_bases_admin()
    return render_template("admin/filiais.html", bases=bases)


@app.route("/admin/filiais/<string:base_id>/editar", methods=["POST"])
@admin_required
def admin_editar_filial(base_id):
    try:
        admin_atualizar_base(base_id, request.form.get("nome", ""))
        flash("Nome da filial atualizado.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_filiais"))


@app.route("/admin/filiais/<string:base_id>/excluir", methods=["POST"])
@admin_required
def admin_excluir_filial(base_id):
    try:
        base = admin_excluir_base(base_id)
        flash(
            f"Filial {base['codigo']} — {base['nome']} excluída com todos os dados vinculados.",
            "success",
        )
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_filiais"))


@app.route("/admin/usuarios/novo", methods=["POST"])
@admin_required
def admin_novo_usuario():
    try:
        admin_criar_usuario(
            request.form.get("base_id", ""),
            request.form.get("usuario", ""),
            request.form.get("nome", ""),
            request.form.get("nivel", ""),
            request.form.get("senha", ""),
        )
        flash("Usuário criado com sucesso.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    base_id = request.form.get("base_id", "")
    return redirect(url_for("admin_usuarios", base_id=base_id) if base_id else url_for("admin_usuarios"))


@app.route("/admin/usuarios/<string:user_id>/senha", methods=["POST"])
@admin_required
def admin_reset_senha(user_id):
    user = obter_usuario_por_id(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_usuarios"))

    nova_senha = request.form.get("nova_senha", "")
    try:
        admin_resetar_senha(user_id, nova_senha)
        flash(f"Senha de {user['usuario']} (Filial {user['base_codigo']}) redefinida.", "success")
    except ValueError as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin_usuarios", base_id=user["base_id"]))


@app.route("/admin/usuarios/<string:user_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_user(user_id):
    user = obter_usuario_por_id(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_usuarios"))

    ativo = 0 if user["ativo"] else 1
    admin_toggle_usuario(user_id, ativo)
    estado = "ativado" if ativo else "desativado"
    flash(f"Usuário {user['usuario']} {estado}.", "success")
    return redirect(url_for("admin_usuarios", base_id=user["base_id"]))


@app.route("/admin/usuarios/<string:user_id>/editar", methods=["POST"])
@admin_required
def admin_editar_usuario(user_id):
    user = obter_usuario_por_id(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_usuarios"))

    try:
        admin_atualizar_usuario(
            user_id,
            request.form.get("nome", ""),
            request.form.get("nivel", ""),
        )
        flash("Usuário atualizado.", "success")
    except ValueError as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin_usuarios", base_id=user["base_id"]))


@app.route("/admin/perfil", methods=["GET", "POST"])
@admin_required
def admin_perfil():
    admin = admin_logado()

    if request.method == "POST":
        senha_atual = request.form.get("senha_atual", "")
        nova_senha = request.form.get("nova_senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        if nova_senha != confirmar:
            flash("As senhas não coincidem.", "error")
            return render_template("admin/perfil.html", admin=admin)

        try:
            admin_alterar_senha_admin(admin["id"], senha_atual, nova_senha)
            flash("Senha de administrador alterada.", "success")
            return redirect(url_for("admin_perfil"))
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template("admin/perfil.html", admin=admin)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
