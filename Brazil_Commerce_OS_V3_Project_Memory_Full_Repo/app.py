from __future__ import annotations

from datetime import datetime
import uuid
import re
from docx.shared import Pt
from html import escape
from pathlib import Path
from io import BytesIO

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

import pandas as pd
import streamlit as st

from agent import route_request
from tools.market import run_market_research
from tools.report_generator import generate_market_docx, generate_market_pdf
from tools.operations import run_operations
from tools.marketing import load_creator_file, score_creators, explain_creator_fit, analyse_creator_dataset, discover_creators
from tools.finance import load_finance_file, analyse_finance
from llm import chat
from config import DEMO_MODE, SERPER_API_KEY


# =========================================================
# App setup
# =========================================================
BASE = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Brazil Commerce OS",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# Internationalisation (UI + AI output instruction)
# =========================================================
LANG_OPTIONS = {
    "简体中文": "zh",
    "English": "en",
    "Português (Brasil)": "pt-BR",
}

I18N = {
    "zh": {
        "app_name": "Brazil Commerce OS",
        "tagline": "巴西跨境电商智能运营平台",
        "mvp": "AI Commerce Agent · Working Prototype",
        "language": "语言 / Language",
        "workspace": "工作区",
        "nav_command": "指挥中心",
        "nav_market": "01 市场情报",
        "nav_ops": "02 电商运营",
        "nav_marketing": "03 营销 / 创作者",
        "nav_finance": "04 财务与绩效",
        "nav_audit": "审计追踪",
        "ai_status": "AI 状态",
        "ai_live": "LLM 已连接",
        "ai_demo": "Demo 模式",
        "search_live": "实时搜索已连接",
        "search_offline": "实时搜索未连接",
        "home_title": "从一个商业目标开始",
        "home_subtitle": "Agent 会先判断任务类型，再进入对应工作流。四个模块可独立使用，也可通过稳定 ID 和数据结构连接。",
        "goal_label": "你想完成什么？ *",
        "goal_ph": "例如：我想把猫爬架卖到巴西，先帮我判断市场机会和需要验证的风险。",
        "route": "分析任务",
        "route_to": "建议工作流",
        "open_module": "打开对应模块",
        "copilot": "AI Copilot",
        "copilot_sub": "适合问概念、流程、指标和下一步怎么做。",
        "copilot_label": "输入问题",
        "copilot_ph": "例如：ROAS 和利润有什么区别？",
        "ask": "Ask Copilot",
        "required": "请完成所有必填项。",
        "empty_goal": "请先输入一个目标。",
        "empty_question": "请输入一个问题。",
        "market_card_title": "市场与产品情报",
        "market_card_desc": "实时检索公开证据，分析市场、竞争、价格、渠道、消费者需求与监管。",
        "ops_card_title": "电商规划与运营",
        "ops_card_desc": "基于已批准的商品事实生成本地化 listing 和 launch checklist，不猜关键商业事实。",
        "marketing_card_title": "营销 / Creator / 内容",
        "marketing_card_desc": "读取真实 Creator 数据，规则评分 + AI 解释，并形成 campaign 与内容执行建议。",
        "finance_card_title": "财务与绩效情报",
        "finance_card_desc": "Python 做确定性计算；AI 负责解释利润、漏斗和下一步动作。",
        "market_title": "01 Market & Product Intelligence",
        "market_sub": "先定义研究问题，再检索 evidence；没有证据就明确标记不足，不让 LLM 编数字。",
        "rules": "方法与规则",
        "country": "Country / Market *",
        "product": "Product / Category *",
        "product_ph": "例如：猫爬架 / 家用咖啡机",
        "platform_optional": "Platform（选填）",
        "price_optional": "Expected Price Range（选填）",
        "price_ph": "例如：R$120–350",
        "research_objective": "Research Objective *",
        "research_objective_ph": "例如：判断该类目是否值得进入巴西，并了解市场需求、主要竞争、价格带、渠道和监管风险。",
        "research_dims": "Research Dimensions *",
        "run_market": "Run Market Research",
        "researching": "正在规划检索 → 获取 evidence → 生成研究备忘录…",
        "research_memo": "Research Memo",
        "evidence_register": "Evidence Register",
        "evidence_count": "证据条数",
        "download_memo": "下载研究备忘录 (.md)",
        "mode_live": "LIVE SEARCH",
        "mode_demo": "DEMO SEARCH",
        "ops_title": "02 E-commerce Planning & Operations",
        "ops_sub": "从商品资料到本地化上架与启动清单，把市场机会转成可执行的电商运营方案。",
        "merchant_id": "Merchant ID *",
        "product_id": "Product ID *",
        "sku": "SKU *",
        "product_name": "Product Name *",
        "product_name_ph": "例如：折叠式猫爬架",
        "platform": "Platform *",
        "approved_facts": "Approved Product Facts *",
        "approved_facts_ph": "只填写已确认的产品事实，例如材料、尺寸、功能、包装、已核实认证等。",
        "selling_price": "Selling Price（选填）",
        "inventory": "Inventory（选填）",
        "unit_cost": "Unit Cost（选填）",
        "generate_launch": "Generate Launch Pack",
        "generating_launch": "正在生成本地化 Listing + Launch Control Pack…",
        "missing": "缺失字段",
        "launch_pack": "Launch Pack",
        "ops_language_note": "面向巴西消费者的 Listing 默认以巴西葡萄牙语生成，这是当前 Operations 工具的业务设定。",
        "download_launch": "下载 Launch Pack",
        "marketing_title": "03 Marketing / Creator / Content",
        "marketing_sub": "整合 Creator 数据、筛选逻辑与 AI 分析，形成更清晰的达人选择和内容执行方案。",
        "campaign_id": "Campaign ID *",
        "product_sku": "Product / SKU *",
        "campaign_objective": "Campaign Objective *",
        "category": "Category *",
        "category_ph": "例如：Pet / Beauty",
        "creator_budget": "Creator Budget BRL（选填）",
        "brand_brief": "Approved Product / Brand Brief *",
        "brand_brief_ph": "填写已确认的品牌与商品要求、禁用 claims、内容方向等。",
        "upload_creator": "上传 Creator CSV / XLSX *",
        "creator_empty": "请上传真实 Creator 数据后再做 shortlist。第一版支持 CSV / Excel。",
        "rows_loaded": "已载入 Creator 行数",
        "build_shortlist": "Build Creator Shortlist",
        "shortlist": "Deterministic Shortlist",
        "fit_analysis": "AI Fit Analysis",
        "analysing_fit": "AI 正在解释 Creator fit…",
        "download_creator_template": "下载 Creator CSV 模板",
        "download_creator_analysis": "下载 Creator Analysis (.md)",
        "finance_title": "04 Financial & Performance Intelligence",
        "finance_sub": "把经营数据转成利润、效率和营销表现洞察，帮助定位业务驱动因素与下一步动作。",
        "upload_finance": "上传 Finance CSV / XLSX / JSON *",
        "finance_empty": "Profitability = Incomplete。请先上传经营数据。",
        "run_finance": "Run Financial Analysis",
        "net_sales": "Net Sales",
        "aov": "AOV",
        "roas": "ROAS",
        "contribution_profit": "Contribution Profit",
        "contribution_margin": "Contribution Margin",
        "incomplete": "Incomplete",
        "field_mapping": "Field Mapping",
        "ai_advisor": "AI Advisor",
        "analysing_finance": "正在计算并生成管理层解释…",
        "download_finance_template": "下载 Finance CSV 模板",
        "download_finance_analysis": "下载 Finance Analysis (.md)",
        "audit_title": "Audit Trail",
        "audit_sub": "当前浏览器会话中的运行记录。用于演示与调试，不等同于生产级持久化日志。",
        "no_history": "还没有运行记录。",
        "clear_history": "清空本次会话记录",
        "history_cleared": "已清空。",
        "source_priority": "Source priority：政府/监管 > 行业协会 > 公司披露 > 专业研究机构 > 可靠行业媒体 > Marketplace/Search evidence。",
        "market_rule_1": "关键数字必须有来源；缺少可靠证据时标记 insufficient evidence。",
        "market_rule_2": "公开 Web Search 适合 high-level intelligence；精准平台商业数据仍需 FastMoss / 平台 / 商家数据。",
        "ops_rule_1": "Product / SKU / Order 使用稳定 ID，方便后续 Marketing 与 Finance 关联。",
        "ops_rule_2": "价格、库存、认证、平台费、退款政策等不能由 LLM 猜。",
        "marketing_rule_1": "Creator 身份必须来自真实来源；Fit score 是内部规则评分，不是平台官方排名。",
        "marketing_rule_2": "建联、合同、发布、付款等高影响动作保留人工审批。",
        "finance_rule_1": "财务数字由 Python 计算；LLM 只解释，不自由重算。",
        "finance_rule_2": "关键成本缺失时 Profitability 必须保持 Incomplete，Missing ≠ 0。",
    },
    "en": {
        "app_name": "Brazil Commerce OS",
        "tagline": "AI operating system for cross-border commerce in Brazil",
        "mvp": "AI Commerce Agent · Working Prototype",
        "language": "Language",
        "workspace": "Workspace",
        "nav_command": "Command Center",
        "nav_market": "01 Market Intelligence",
        "nav_ops": "02 E-commerce Operations",
        "nav_marketing": "03 Marketing / Creator",
        "nav_finance": "04 Finance & Performance",
        "nav_audit": "Audit Trail",
        "ai_status": "System status",
        "ai_live": "LLM connected",
        "ai_demo": "Demo mode",
        "search_live": "Live search connected",
        "search_offline": "Live search offline",
        "home_title": "Start with a business objective",
        "home_subtitle": "The agent routes each task into the right workflow. Modules can run independently and connect through stable IDs and shared data structures.",
        "goal_label": "What do you want to achieve? *",
        "goal_ph": "Example: I want to sell cat trees in Brazil. Help me assess the opportunity and key risks first.",
        "route": "Analyse request",
        "route_to": "Recommended workflow",
        "open_module": "Open module",
        "copilot": "AI Copilot",
        "copilot_sub": "Use this for concepts, metrics, workflows and next-step questions.",
        "copilot_label": "Ask a question",
        "copilot_ph": "Example: What is the difference between ROAS and profit?",
        "ask": "Ask Copilot",
        "required": "Please complete all required fields.",
        "empty_goal": "Please enter a business objective first.",
        "empty_question": "Please enter a question.",
        "market_card_title": "Market & Product Intelligence",
        "market_card_desc": "Retrieve live public evidence and analyse market demand, competition, pricing, channels, consumers and regulation.",
        "ops_card_title": "E-commerce Planning & Operations",
        "ops_card_desc": "Generate localised listings and launch controls from approved product facts without inventing commercial facts.",
        "marketing_card_title": "Marketing / Creator / Content",
        "marketing_card_desc": "Use real creator data for deterministic scoring, AI fit explanations and campaign/content planning.",
        "finance_card_title": "Financial & Performance Intelligence",
        "finance_card_desc": "Python handles deterministic calculations; AI explains profit drivers, funnel performance and next actions.",
        "market_title": "01 Market & Product Intelligence",
        "market_sub": "Define the research question first, then retrieve evidence. If evidence is weak, the system says so instead of inventing numbers.",
        "rules": "Method & rules",
        "country": "Country / Market *",
        "product": "Product / Category *",
        "product_ph": "Example: cat tree / home espresso maker",
        "platform_optional": "Platform (optional)",
        "price_optional": "Expected Price Range (optional)",
        "price_ph": "Example: R$120–350",
        "research_objective": "Research Objective *",
        "research_objective_ph": "Example: assess whether this category is worth entering in Brazil and understand demand, competition, pricing, channels and regulatory risks.",
        "research_dims": "Research Dimensions *",
        "run_market": "Run Market Research",
        "researching": "Planning queries → retrieving evidence → generating research memo…",
        "research_memo": "Research Memo",
        "evidence_register": "Evidence Register",
        "evidence_count": "Evidence items",
        "download_memo": "Download research memo (.md)",
        "mode_live": "LIVE SEARCH",
        "mode_demo": "DEMO SEARCH",
        "ops_title": "02 E-commerce Planning & Operations",
        "ops_sub": "Turn an opportunity into a launch-ready commerce package. Listings can be generated; business facts cannot be guessed.",
        "merchant_id": "Merchant ID *",
        "product_id": "Product ID *",
        "sku": "SKU *",
        "product_name": "Product Name *",
        "product_name_ph": "Example: foldable cat tree",
        "platform": "Platform *",
        "approved_facts": "Approved Product Facts *",
        "approved_facts_ph": "Only confirmed facts such as material, dimensions, functions, packaging and verified certifications.",
        "selling_price": "Selling Price (optional)",
        "inventory": "Inventory (optional)",
        "unit_cost": "Unit Cost (optional)",
        "generate_launch": "Generate Launch Pack",
        "generating_launch": "Generating localised listing + launch control pack…",
        "missing": "Missing fields",
        "launch_pack": "Launch Pack",
        "ops_language_note": "Consumer-facing Brazil listings are generated in Brazilian Portuguese by design in the current Operations tool.",
        "download_launch": "Download Launch Pack",
        "marketing_title": "03 Marketing / Creator / Content",
        "marketing_sub": "Real creator data → deterministic scoring → AI fit explanation. No real data means no invented creators.",
        "campaign_id": "Campaign ID *",
        "product_sku": "Product / SKU *",
        "campaign_objective": "Campaign Objective *",
        "category": "Category *",
        "category_ph": "Example: Pet / Beauty",
        "creator_budget": "Creator Budget BRL (optional)",
        "brand_brief": "Approved Product / Brand Brief *",
        "brand_brief_ph": "Confirmed product/brand requirements, prohibited claims, content direction and constraints.",
        "upload_creator": "Upload Creator CSV / XLSX *",
        "creator_empty": "Upload real creator data before building a shortlist. CSV and Excel are supported.",
        "rows_loaded": "Creator rows loaded",
        "build_shortlist": "Build Creator Shortlist",
        "shortlist": "Deterministic Shortlist",
        "fit_analysis": "AI Fit Analysis",
        "analysing_fit": "AI is explaining creator fit…",
        "download_creator_template": "Download Creator CSV template",
        "download_creator_analysis": "Download Creator Analysis (.md)",
        "finance_title": "04 Financial & Performance Intelligence",
        "finance_sub": "Validate data first, calculate second, explain third. No real file means no fake profitability.",
        "upload_finance": "Upload Finance CSV / XLSX / JSON *",
        "finance_empty": "Profitability = Incomplete. Upload operating data first.",
        "run_finance": "Run Financial Analysis",
        "net_sales": "Net Sales",
        "aov": "AOV",
        "roas": "ROAS",
        "contribution_profit": "Contribution Profit",
        "contribution_margin": "Contribution Margin",
        "incomplete": "Incomplete",
        "field_mapping": "Field Mapping",
        "ai_advisor": "AI Advisor",
        "analysing_finance": "Calculating results and generating management commentary…",
        "download_finance_template": "Download Finance CSV template",
        "download_finance_analysis": "Download Finance Analysis (.md)",
        "audit_title": "Audit Trail",
        "audit_sub": "Run history for the current browser session. This is a prototype audit view, not production-grade persistent logging.",
        "no_history": "No runs recorded yet.",
        "clear_history": "Clear session history",
        "history_cleared": "History cleared.",
        "source_priority": "Source priority: government/regulator > industry association > company disclosure > professional research > reliable industry media > marketplace/search evidence.",
        "market_rule_1": "Important quantitative claims require evidence; weak evidence must be labelled insufficient.",
        "market_rule_2": "Web search supports high-level intelligence; precise commercial data still requires FastMoss, platform or merchant data.",
        "ops_rule_1": "Product / SKU / Order use stable IDs so Marketing and Finance can join later.",
        "ops_rule_2": "Price, inventory, certification, platform fees and refund policies must not be invented by the LLM.",
        "marketing_rule_1": "Creator identities must come from real sources. Fit score is an internal rule score, not a platform ranking.",
        "marketing_rule_2": "Outreach, contracts, publishing and payments remain human-approved in the MVP.",
        "finance_rule_1": "Financial values are calculated by Python. The LLM explains but does not freely recalculate.",
        "finance_rule_2": "If critical costs are missing, Profitability remains Incomplete. Missing ≠ 0.",
    },
    "pt-BR": {
        "app_name": "Brazil Commerce OS",
        "tagline": "Plataforma inteligente para operações de comércio no Brasil",
        "mvp": "AI Commerce Agent · Protótipo Funcional",
        "language": "Idioma",
        "workspace": "Área de trabalho",
        "nav_command": "Central de Comando",
        "nav_market": "01 Inteligência de Mercado",
        "nav_ops": "02 Operações de E-commerce",
        "nav_marketing": "03 Marketing / Criadores",
        "nav_finance": "04 Finanças e Desempenho",
        "nav_audit": "Trilha de Auditoria",
        "ai_status": "Status do sistema",
        "ai_live": "LLM conectado",
        "ai_demo": "Modo demo",
        "search_live": "Busca em tempo real conectada",
        "search_offline": "Busca em tempo real offline",
        "home_title": "Comece com um objetivo de negócio",
        "home_subtitle": "O agente direciona cada tarefa para o fluxo adequado. Os módulos funcionam de forma independente e podem ser conectados por IDs estáveis e estruturas de dados comuns.",
        "goal_label": "O que você quer alcançar? *",
        "goal_ph": "Exemplo: quero vender arranhadores para gatos no Brasil. Primeiro avalie a oportunidade e os principais riscos.",
        "route": "Analisar solicitação",
        "route_to": "Fluxo recomendado",
        "open_module": "Abrir módulo",
        "copilot": "AI Copilot",
        "copilot_sub": "Use para dúvidas sobre conceitos, métricas, fluxos e próximos passos.",
        "copilot_label": "Faça uma pergunta",
        "copilot_ph": "Exemplo: qual é a diferença entre ROAS e lucro?",
        "ask": "Perguntar ao Copilot",
        "required": "Preencha todos os campos obrigatórios.",
        "empty_goal": "Digite primeiro um objetivo de negócio.",
        "empty_question": "Digite uma pergunta.",
        "market_card_title": "Inteligência de Mercado e Produto",
        "market_card_desc": "Busca evidências públicas em tempo real e analisa demanda, concorrência, preços, canais, consumidores e regulamentação.",
        "ops_card_title": "Planejamento e Operações de E-commerce",
        "ops_card_desc": "Gera listings localizados e controles de lançamento a partir de fatos aprovados, sem inventar dados comerciais.",
        "marketing_card_title": "Marketing / Criadores / Conteúdo",
        "marketing_card_desc": "Usa dados reais de criadores para scoring determinístico, análise de fit e planejamento de campanhas e conteúdo.",
        "finance_card_title": "Inteligência Financeira e de Desempenho",
        "finance_card_desc": "Python faz os cálculos determinísticos; a IA explica drivers de lucro, funil e próximos passos.",
        "market_title": "01 Inteligência de Mercado e Produto",
        "market_sub": "Primeiro define a pergunta de pesquisa, depois busca evidências. Se a evidência for fraca, o sistema sinaliza isso em vez de inventar números.",
        "rules": "Método e regras",
        "country": "País / Mercado *",
        "product": "Produto / Categoria *",
        "product_ph": "Exemplo: arranhador para gatos / cafeteira espresso",
        "platform_optional": "Plataforma (opcional)",
        "price_optional": "Faixa de preço esperada (opcional)",
        "price_ph": "Exemplo: R$120–350",
        "research_objective": "Objetivo da Pesquisa *",
        "research_objective_ph": "Exemplo: avaliar se vale a pena entrar nesta categoria no Brasil e entender demanda, concorrência, preços, canais e riscos regulatórios.",
        "research_dims": "Dimensões da Pesquisa *",
        "run_market": "Executar Pesquisa de Mercado",
        "researching": "Planejando buscas → coletando evidências → gerando relatório…",
        "research_memo": "Memorando de Pesquisa",
        "evidence_register": "Registro de Evidências",
        "evidence_count": "Itens de evidência",
        "download_memo": "Baixar memorando (.md)",
        "mode_live": "BUSCA AO VIVO",
        "mode_demo": "BUSCA DEMO",
        "ops_title": "02 Planejamento e Operações de E-commerce",
        "ops_sub": "Transforme uma oportunidade em um pacote pronto para lançamento. O listing pode ser gerado; fatos comerciais não podem ser adivinhados.",
        "merchant_id": "Merchant ID *",
        "product_id": "Product ID *",
        "sku": "SKU *",
        "product_name": "Nome do Produto *",
        "product_name_ph": "Exemplo: arranhador dobrável para gatos",
        "platform": "Plataforma *",
        "approved_facts": "Fatos Aprovados do Produto *",
        "approved_facts_ph": "Somente fatos confirmados: material, dimensões, funções, embalagem e certificações verificadas.",
        "selling_price": "Preço de Venda (opcional)",
        "inventory": "Estoque (opcional)",
        "unit_cost": "Custo Unitário (opcional)",
        "generate_launch": "Gerar Pacote de Lançamento",
        "generating_launch": "Gerando listing localizado + pacote de controle de lançamento…",
        "missing": "Campos ausentes",
        "launch_pack": "Pacote de Lançamento",
        "ops_language_note": "Os listings voltados ao consumidor brasileiro são gerados em português do Brasil por padrão no módulo atual de Operações.",
        "download_launch": "Baixar pacote de lançamento",
        "marketing_title": "03 Marketing / Criadores / Conteúdo",
        "marketing_sub": "Dados reais de criadores → scoring determinístico → explicação de fit por IA. Sem dados reais, sem criadores inventados.",
        "campaign_id": "Campaign ID *",
        "product_sku": "Produto / SKU *",
        "campaign_objective": "Objetivo da Campanha *",
        "category": "Categoria *",
        "category_ph": "Exemplo: Pet / Beauty",
        "creator_budget": "Orçamento para Criadores em BRL (opcional)",
        "brand_brief": "Brief Aprovado de Produto / Marca *",
        "brand_brief_ph": "Requisitos confirmados, claims proibidos, direção de conteúdo e restrições.",
        "upload_creator": "Enviar Creator CSV / XLSX *",
        "creator_empty": "Envie dados reais de criadores antes de criar a shortlist. CSV e Excel são suportados.",
        "rows_loaded": "Linhas de criadores carregadas",
        "build_shortlist": "Criar Shortlist de Criadores",
        "shortlist": "Shortlist Determinística",
        "fit_analysis": "Análise de Fit por IA",
        "analysing_fit": "A IA está explicando o fit dos criadores…",
        "download_creator_template": "Baixar modelo CSV de Criadores",
        "download_creator_analysis": "Baixar análise de criadores (.md)",
        "finance_title": "04 Inteligência Financeira e de Desempenho",
        "finance_sub": "Valide os dados, calcule e só depois explique. Sem arquivo real, não existe lucratividade falsa.",
        "upload_finance": "Enviar Finance CSV / XLSX / JSON *",
        "finance_empty": "Profitability = Incomplete. Envie primeiro os dados operacionais.",
        "run_finance": "Executar Análise Financeira",
        "net_sales": "Vendas Líquidas",
        "aov": "AOV",
        "roas": "ROAS",
        "contribution_profit": "Lucro de Contribuição",
        "contribution_margin": "Margem de Contribuição",
        "incomplete": "Incompleto",
        "field_mapping": "Mapeamento de Campos",
        "ai_advisor": "AI Advisor",
        "analysing_finance": "Calculando resultados e gerando comentário gerencial…",
        "download_finance_template": "Baixar modelo CSV Financeiro",
        "download_finance_analysis": "Baixar análise financeira (.md)",
        "audit_title": "Trilha de Auditoria",
        "audit_sub": "Histórico de execução da sessão atual do navegador. É uma visão de protótipo, não um log persistente de produção.",
        "no_history": "Nenhuma execução registrada ainda.",
        "clear_history": "Limpar histórico da sessão",
        "history_cleared": "Histórico limpo.",
        "source_priority": "Prioridade de fontes: governo/regulador > associação setorial > divulgação de empresas > pesquisa profissional > mídia setorial confiável > evidência de marketplace/busca.",
        "market_rule_1": "Dados quantitativos importantes exigem evidência; evidência fraca deve ser marcada como insuficiente.",
        "market_rule_2": "Web search serve para inteligência de alto nível; dados comerciais precisos ainda exigem FastMoss, plataforma ou dados do lojista.",
        "ops_rule_1": "Product / SKU / Order usam IDs estáveis para conexão posterior com Marketing e Finance.",
        "ops_rule_2": "Preço, estoque, certificação, taxas de plataforma e política de reembolso não podem ser inventados pela IA.",
        "marketing_rule_1": "A identidade dos criadores deve vir de fontes reais. Fit score é um score interno, não ranking oficial da plataforma.",
        "marketing_rule_2": "Contato, contratos, publicação e pagamentos permanecem com aprovação humana no MVP.",
        "finance_rule_1": "Os valores financeiros são calculados em Python. A IA explica, mas não recalcula livremente.",
        "finance_rule_2": "Se custos críticos estiverem ausentes, Profitability permanece Incomplete. Missing ≠ 0.",
    },
}

AI_LANGUAGE_INSTRUCTION = {
    "zh": "Respond in clear Simplified Chinese. Keep standard business/technical English terms where useful.",
    "en": "Respond in concise professional English.",
    "pt-BR": "Respond in natural Brazilian Portuguese (pt-BR), not European Portuguese.",
}

MARKET_UI = {
    "zh": {
        "eyebrow": "市场与产品情报",
        "title": "把一个产品想法，变成有证据的市场判断",
        "subtitle": "输入产品和目标市场。系统会检索公开信息、交叉整理关键证据，并生成结构化市场研究报告。即使问题很简单，也会按完整研究框架展开。",
        "feature_1": "实时公开信息检索",
        "feature_2": "基于来源的客观分析",
        "feature_3": "中文 / English / Português 输出",
        "market": "目标市场 *",
        "market_help": "可输入任意国家或区域，例如 Brazil、Mexico、Southeast Asia。",
        "product": "产品 / 类目 *",
        "product_ph": "例如：猫爬架、家用咖啡机、美妆工具",
        "question": "你最想回答的问题（选填）",
        "question_ph": "例如：猫爬架在巴西好卖吗？如果留空，系统会自动做完整的市场进入评估。",
        "advanced": "高级研究设置",
        "platform": "重点平台（选填）",
        "price": "预期售价区间（选填）",
        "dimensions": "重点研究维度",
        "run": "生成市场研究报告",
        "spinner": "正在规划研究 → 检索公开信息 → 整理证据 → 生成报告…",
        "default_objective": "评估该产品在目标市场的商业机会，包括市场需求、增长信号、消费者、竞争格局、价格带、渠道、监管与主要进入风险，并给出客观的下一步验证建议。",
        "report": "市场研究报告",
        "report_sub": "基于本次检索到的公开证据生成。关键事实应以来源为准，证据不足处应明确说明。",
        "sources": "来源与证据",
        "sources_sub": "这里保留报告使用的原始检索证据，便于核查；正常阅读报告时无需展开。",
        "download": "下载报告 (.md)",
        "evidence": "已纳入证据",
        "live": "实时研究",
        "demo": "演示研究",
        "need_product": "请输入产品 / 类目。",
    },
    "en": {
        "eyebrow": "MARKET & PRODUCT INTELLIGENCE",
        "title": "Turn a product idea into an evidence-backed market view",
        "subtitle": "Enter a product and target market. The system retrieves public information, structures the evidence and produces a market research report. A simple question is expanded into a complete research framework.",
        "feature_1": "Live public-web research",
        "feature_2": "Evidence-backed analysis",
        "feature_3": "Chinese / English / Portuguese output",
        "market": "Target market *",
        "market_help": "Enter any country or region, e.g. Brazil, Mexico or Southeast Asia.",
        "product": "Product / category *",
        "product_ph": "Example: cat tree, home espresso maker, beauty tools",
        "question": "Key business question (optional)",
        "question_ph": "Example: Are cat trees attractive in Brazil? Leave blank for a full market-entry assessment.",
        "advanced": "Advanced research settings",
        "platform": "Priority platform (optional)",
        "price": "Expected price range (optional)",
        "dimensions": "Priority research dimensions",
        "run": "Generate market research report",
        "spinner": "Planning research → retrieving public information → structuring evidence → generating report…",
        "default_objective": "Assess the commercial opportunity for this product in the target market, including demand and growth signals, consumers, competition, price bands, channels, regulation and major entry risks, with objective next-step validation priorities.",
        "report": "Market research report",
        "report_sub": "Generated from public evidence retrieved for this run. Key facts should remain source-backed and evidence gaps should be stated explicitly.",
        "sources": "Sources & evidence",
        "sources_sub": "Raw evidence used by the report is retained here for verification; most users do not need to expand it during normal reading.",
        "download": "Download report (.md)",
        "evidence": "Evidence items",
        "live": "Live research",
        "demo": "Demo research",
        "need_product": "Please enter a product / category.",
    },
    "pt-BR": {
        "eyebrow": "INTELIGÊNCIA DE MERCADO E PRODUTO",
        "title": "Transforme uma ideia de produto em uma visão de mercado baseada em evidências",
        "subtitle": "Informe o produto e o mercado-alvo. O sistema pesquisa informações públicas, organiza as evidências e produz um relatório de mercado estruturado. Mesmo uma pergunta simples é ampliada para um framework completo de pesquisa.",
        "feature_1": "Pesquisa pública em tempo real",
        "feature_2": "Análise baseada em evidências",
        "feature_3": "Saída em chinês / inglês / português",
        "market": "Mercado-alvo *",
        "market_help": "Informe qualquer país ou região, por exemplo Brasil, México ou Sudeste Asiático.",
        "product": "Produto / categoria *",
        "product_ph": "Ex.: árvore para gatos, cafeteira doméstica, acessórios de beleza",
        "question": "Pergunta principal de negócio (opcional)",
        "question_ph": "Ex.: Vale a pena vender árvores para gatos no Brasil? Deixe em branco para uma avaliação completa de entrada no mercado.",
        "advanced": "Configurações avançadas da pesquisa",
        "platform": "Plataforma prioritária (opcional)",
        "price": "Faixa de preço esperada (opcional)",
        "dimensions": "Dimensões prioritárias da pesquisa",
        "run": "Gerar relatório de pesquisa de mercado",
        "spinner": "Planejando pesquisa → buscando informações públicas → estruturando evidências → gerando relatório…",
        "default_objective": "Avaliar a oportunidade comercial do produto no mercado-alvo, incluindo sinais de demanda e crescimento, consumidores, concorrência, faixas de preço, canais, regulamentação e principais riscos de entrada, com prioridades objetivas para validação.",
        "report": "Relatório de pesquisa de mercado",
        "report_sub": "Gerado a partir das evidências públicas recuperadas nesta execução. Fatos importantes devem permanecer sustentados por fontes e lacunas de evidência devem ser explicitadas.",
        "sources": "Fontes e evidências",
        "sources_sub": "As evidências brutas usadas no relatório ficam aqui para verificação; na leitura normal, não é necessário expandir esta seção.",
        "download": "Baixar relatório (.md)",
        "evidence": "Itens de evidência",
        "live": "Pesquisa ao vivo",
        "demo": "Pesquisa demo",
        "need_product": "Informe um produto / categoria.",
    },
}

DIMENSIONS = [
    "Market size & growth",
    "Competition",
    "Pricing",
    "Channels",
    "Consumer need",
    "Regulation",
    "TikTok / social commerce signals",
]

DIMENSION_LABELS = {
    "zh": {
        "Market size & growth": "市场规模与增长",
        "Competition": "竞争格局",
        "Pricing": "定价",
        "Channels": "渠道",
        "Consumer need": "消费者需求",
        "Regulation": "监管 / 合规",
        "TikTok / social commerce signals": "TikTok / 社交电商信号",
    },
    "en": {x: x for x in DIMENSIONS},
    "pt-BR": {
        "Market size & growth": "Tamanho e crescimento do mercado",
        "Competition": "Concorrência",
        "Pricing": "Preços",
        "Channels": "Canais",
        "Consumer need": "Necessidades do consumidor",
        "Regulation": "Regulamentação / compliance",
        "TikTok / social commerce signals": "Sinais de TikTok / social commerce",
    },
}

CAMPAIGN_OBJECTIVES = [
    "Sales / Conversion",
    "Brand Awareness",
    "Product Seeding",
    "LIVE Traffic",
]

CAMPAIGN_OBJECTIVE_LABELS = {
    "zh": {
        "Sales / Conversion": "销售 / 转化",
        "Brand Awareness": "品牌认知",
        "Product Seeding": "产品种草",
        "LIVE Traffic": "直播引流",
    },
    "en": {x: x for x in CAMPAIGN_OBJECTIVES},
    "pt-BR": {
        "Sales / Conversion": "Vendas / Conversão",
        "Brand Awareness": "Reconhecimento de Marca",
        "Product Seeding": "Seeding de Produto",
        "LIVE Traffic": "Tráfego para LIVE",
    },
}


# =========================================================
# Styling
# =========================================================
st.markdown(
    """
<style>
:root {
    --bcos-navy: #071A35;
    --bcos-navy-2: #0B2447;
    --bcos-orange: #FF5A4F;
    --bcos-green: #159A6A;
    --bcos-bg: #F6F8FB;
    --bcos-line: #E7EAF0;
    --bcos-text: #1F2937;
    --bcos-muted: #667085;
}

html, body, [class*="css"] {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
}

.stApp { background: var(--bcos-bg); }
.block-container {
    max-width: 1280px;
    padding-top: 2.0rem;
    padding-bottom: 4rem;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #071A35 0%, #081F3F 100%);
    border-right: 1px solid rgba(255,255,255,.06);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div {
    color: #EAF0F8;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {
    color: #EAF0F8 !important;
}

h1, h2, h3 {
    letter-spacing: -0.025em;
    color: #202634;
}
h1 { font-weight: 760 !important; }
h2 { font-weight: 720 !important; }

.bcos-brand {
    padding: 4px 0 14px 0;
}
.bcos-brand-title {
    font-size: 1.2rem;
    font-weight: 760;
    color: white;
    letter-spacing: -.02em;
}
.bcos-brand-sub {
    font-size: .78rem;
    color: #9FB0C8;
    margin-top: 4px;
}

.bcos-hero {
    background: linear-gradient(135deg, #071A35 0%, #0F315D 70%, #174D74 100%);
    border-radius: 24px;
    padding: 34px 36px;
    color: white;
    margin: 4px 0 24px 0;
    box-shadow: 0 18px 48px rgba(7,26,53,.12);
}
.bcos-hero h1 {
    color: white !important;
    margin: 0 0 8px 0;
    font-size: 2.25rem;
}
.bcos-hero p {
    color: #D8E3F1;
    font-size: 1rem;
    max-width: 850px;
    margin: 0;
    line-height: 1.65;
}

.bcos-kicker {
    display: inline-block;
    font-size: .74rem;
    font-weight: 700;
    letter-spacing: .07em;
    text-transform: uppercase;
    color: #FFB1A8;
    margin-bottom: 10px;
}

.bcos-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
    margin: 18px 0 30px 0;
}
.bcos-card {
    background: #FFFFFF;
    border: 1px solid var(--bcos-line);
    border-radius: 18px;
    padding: 22px 22px 20px 22px;
    min-height: 160px;
    box-shadow: 0 5px 18px rgba(16,24,40,.035);
}
.bcos-card-number {
    color: #FF5A4F;
    font-size: .76rem;
    font-weight: 750;
    letter-spacing: .08em;
    margin-bottom: 10px;
}
.bcos-card-title {
    color: #1F2937;
    font-size: 1.12rem;
    font-weight: 730;
    line-height: 1.3;
    margin-bottom: 8px;
}
.bcos-card-desc {
    color: #667085;
    font-size: .9rem;
    line-height: 1.62;
}

.bcos-panel {
    background: #FFFFFF;
    border: 1px solid var(--bcos-line);
    border-radius: 18px;
    padding: 22px;
    margin: 10px 0 18px 0;
}

.bcos-status-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 10px;
}
.bcos-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    border-radius: 999px;
    padding: 7px 10px;
    font-size: .76rem;
    font-weight: 650;
    border: 1px solid rgba(255,255,255,.12);
    background: rgba(255,255,255,.06);
    color: #DDE7F3;
}
.bcos-dot-green {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #42D59C;
}
.bcos-dot-amber {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #F5B942;
}

.bcos-section-title {
    font-size: 1.55rem;
    font-weight: 760;
    color: #202634;
    margin: 6px 0 4px 0;
    letter-spacing: -.025em;
}
.bcos-section-sub {
    color: #667085;
    font-size: .94rem;
    margin-bottom: 20px;
    line-height: 1.6;
}
.bcos-eyebrow {
    color: #FF5A4F;
    font-size: .76rem;
    font-weight: 760;
    letter-spacing: .08em;
    text-transform: uppercase;
    margin-bottom: 7px;
}

.bcos-empty {
    border: 1px dashed #C8CFDB;
    background: #FAFBFC;
    border-radius: 16px;
    padding: 22px;
    color: #667085;
    margin: 8px 0 16px 0;
}
.bcos-result-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin: 26px 0 8px 0;
}
.bcos-badge-live {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    background: #E9F8F1;
    color: #067647;
    font-size: .75rem;
    font-weight: 720;
}
.bcos-badge-demo {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    background: #FFF4E5;
    color: #B54708;
    font-size: .75rem;
    font-weight: 720;
}

div[data-testid="stButton"] > button[kind="primary"] {
    background: #FF5A4F;
    border: 1px solid #FF5A4F;
    color: white;
    border-radius: 10px;
    font-weight: 680;
    min-height: 42px;
    box-shadow: none;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #E94C42;
    border-color: #E94C42;
}

div[data-testid="stButton"] > button:not([kind="primary"]) {
    border-radius: 10px;
}

[data-testid="stTextInputRootElement"],
[data-testid="stTextArea"] textarea,
[data-baseweb="select"] > div {
    border-radius: 11px !important;
}

[data-testid="stMetric"] {
    background: white;
    border: 1px solid var(--bcos-line);
    padding: 16px 18px;
    border-radius: 14px;
}

hr { border-color: rgba(255,255,255,.08) !important; }

.bcos-market-hero {
    background: linear-gradient(135deg, #FFFFFF 0%, #F7FAFE 100%);
    border: 1px solid #E1E7F0;
    border-radius: 22px;
    padding: 28px 30px 24px 30px;
    margin: 2px 0 20px 0;
    box-shadow: 0 12px 34px rgba(15, 35, 67, .055);
}
.bcos-market-hero .title {
    font-size: 1.78rem;
    font-weight: 770;
    color: #172033;
    letter-spacing: -.03em;
    line-height: 1.18;
    margin: 2px 0 10px 0;
}
.bcos-market-hero .desc {
    color: #667085;
    line-height: 1.7;
    max-width: 960px;
    font-size: .96rem;
}
.bcos-feature-row {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
    margin-top: 17px;
}
.bcos-feature-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 7px 11px;
    border: 1px solid #DDE5EF;
    border-radius: 999px;
    background: #FFFFFF;
    color: #475467;
    font-size: .77rem;
    font-weight: 650;
}
.bcos-feature-pill:before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #159A6A;
}
.bcos-report-shell {
    background: #FFFFFF;
    border: 1px solid #E1E7F0;
    border-radius: 20px;
    padding: 26px 28px;
    margin-top: 22px;
    box-shadow: 0 10px 28px rgba(15, 35, 67, .045);
}
.bcos-report-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin: 8px 0 2px 0;
}
.bcos-meta-chip {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 6px 10px;
    background: #F2F4F7;
    color: #475467;
    font-size: .74rem;
    font-weight: 650;
}

@media (max-width: 900px) {
    .bcos-grid { grid-template-columns: 1fr; }
    .bcos-hero { padding: 26px 24px; }
    .bcos-hero h1 { font-size: 1.8rem; }
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# Session state
# =========================================================
DEFAULTS = {
    "history": [],
    "ui_language": "简体中文",
    "workspace": "command",
    "market_result": None,
    "ops_result": None,
    "marketing_result": None,
    "finance_result": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

lang_code = LANG_OPTIONS.get(st.session_state.ui_language, "zh")
t = I18N[lang_code]


def ai_lang_instruction() -> str:
    return AI_LANGUAGE_INSTRUCTION[lang_code]


def go_to_module(target: str) -> None:
    st.session_state.workspace = target


def save_history(module: str, title: str, detail: str) -> None:
    st.session_state.history.insert(
        0,
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "module": module,
            "title": title,
            "detail": detail,
        },
    )
    st.session_state.history = st.session_state.history[:100]


def ensure_internal_id(key: str, prefix: str) -> str:
    """Create a stable per-session tracking ID without asking the user to type it."""
    if not st.session_state.get(key):
        st.session_state[key] = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
    return st.session_state[key]


def section_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="bcos-eyebrow">{escape(eyebrow)}</div>
        <div class="bcos-section-title">{escape(title)}</div>
        <div class="bcos-section-sub">{escape(subtitle)}</div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    st.markdown(f'<div class="bcos-empty">{escape(message)}</div>', unsafe_allow_html=True)


def module_cards() -> None:
    cards = [
        ("01", t["market_card_title"], t["market_card_desc"]),
        ("02", t["ops_card_title"], t["ops_card_desc"]),
        ("03", t["marketing_card_title"], t["marketing_card_desc"]),
        ("04", t["finance_card_title"], t["finance_card_desc"]),
    ]
    html = '<div class="bcos-grid">'
    for num, title, desc in cards:
        html += f"""
        <div class="bcos-card">
            <div class="bcos-card-number">MODULE {num}</div>
            <div class="bcos-card-title">{escape(title)}</div>
            <div class="bcos-card-desc">{escape(desc)}</div>
        </div>
        """
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def download_markdown(label: str, content: str, filename: str, key: str) -> None:
    st.download_button(
        label,
        data=content.encode("utf-8"),
        file_name=filename,
        mime="text/markdown",
        key=key,
    )


def build_launch_word(title: str, content: str) -> bytes:
    """Convert the generated Launch Pack markdown-like text into a DOCX."""
    buffer = BytesIO()
    doc = Document()

    p = doc.add_paragraph()
    p.alignment = 1
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(22)

    doc.add_paragraph()

    for raw in content.splitlines():
        line = raw.strip()

        if not line:
            doc.add_paragraph()
            continue

        if line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif re.match(r"^[-*]\s+", line):
            doc.add_paragraph(re.sub(r"^[-*]\s+", "", line), style="List Bullet")
        elif re.match(r"^\d+\.\s+", line):
            doc.add_paragraph(re.sub(r"^\d+\.\s+", "", line), style="List Number")
        else:
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            doc.add_paragraph(clean)

    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def _launch_pdf_font() -> str:
    """Use a built-in CID font so Chinese text can render in PDF."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        return "Helvetica"


def build_launch_pdf(title: str, content: str) -> bytes:
    """Convert the generated Launch Pack markdown-like text into a PDF."""
    buffer = BytesIO()
    font_name = _launch_pdf_font()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "LaunchTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=20,
        leading=25,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    body_style = ParagraphStyle(
        "LaunchBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9.5,
        leading=14,
        spaceAfter=5,
    )
    h1 = ParagraphStyle("LaunchH1", parent=styles["Heading1"], fontName=font_name, fontSize=16, leading=20, spaceAfter=8)
    h2 = ParagraphStyle("LaunchH2", parent=styles["Heading2"], fontName=font_name, fontSize=13, leading=17, spaceAfter=6)
    h3 = ParagraphStyle("LaunchH3", parent=styles["Heading3"], fontName=font_name, fontSize=11, leading=15, spaceAfter=5)

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=46,
        bottomMargin=46,
        title=title,
    )

    story = [Paragraph(title, title_style), Spacer(1, 8)]

    for raw in content.splitlines():
        line = raw.strip()

        if not line:
            story.append(Spacer(1, 5))
            continue

        safe = (
            line.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )
        safe = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", safe)

        if line.startswith("### "):
            story.append(Paragraph(safe[4:], h3))
        elif line.startswith("## "):
            story.append(Paragraph(safe[3:], h2))
        elif line.startswith("# "):
            story.append(Paragraph(safe[2:], h1))
        elif re.match(r"^[-*]\s+", line):
            story.append(Paragraph("• " + re.sub(r"^[-*]\s+", "", safe), body_style))
        else:
            story.append(Paragraph(safe, body_style))

    pdf.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def safe_template_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except Exception:
        return None


def localized_route_copy(module_name: str) -> str:
    copy = {
        "zh": {
            "market": "先进入市场情报：明确目标市场、产品/类目和研究目标，再调用实时搜索获取 evidence。",
            "operations": "先进入电商运营：准备已确认的商品事实、SKU/产品 ID 和目标平台，再生成本地化 listing 与 launch pack。",
            "marketing": "先进入营销 / Creator：需要真实 Creator 或 campaign 数据，系统先做规则评分，再由 AI 解释 fit 与内容方向。",
            "finance": "先进入财务与绩效：上传订单、销售和成本数据，Python 先计算，AI 再解释利润与绩效驱动因素。",
        },
        "en": {
            "market": "Start with Market Intelligence: define the target market, product/category and decision objective, then retrieve live evidence.",
            "operations": "Start with E-commerce Operations: provide approved product facts, stable product/SKU IDs and the target platform before generating the listing and launch pack.",
            "marketing": "Start with Marketing / Creator: use real creator or campaign data, apply deterministic scoring first, then let AI explain fit and content direction.",
            "finance": "Start with Finance & Performance: upload sales/order/cost data, let Python calculate first, then use AI to explain profit and performance drivers.",
        },
        "pt-BR": {
            "market": "Comece por Inteligência de Mercado: defina mercado-alvo, produto/categoria e objetivo da decisão; depois busque evidências em tempo real.",
            "operations": "Comece por Operações: informe fatos aprovados do produto, IDs estáveis de produto/SKU e plataforma-alvo antes de gerar listing e pacote de lançamento.",
            "marketing": "Comece por Marketing / Criadores: use dados reais de criadores ou campanhas, aplique scoring determinístico e depois use a IA para explicar fit e direção de conteúdo.",
            "finance": "Comece por Finanças e Desempenho: envie dados de vendas, pedidos e custos; Python calcula primeiro e a IA explica os drivers de lucro e desempenho.",
        },
    }
    return copy[lang_code].get(module_name, copy[lang_code]["market"])


# =========================================================
# Sidebar
# =========================================================
NAV_LABEL_KEY = {
    "command": "nav_command",
    "market": "nav_market",
    "operations": "nav_ops",
    "marketing": "nav_marketing",
    "finance": "nav_finance",
    "audit": "nav_audit",
}
NAV_OPTIONS = list(NAV_LABEL_KEY.keys())

with st.sidebar:
    st.markdown(
        f"""
        <div class="bcos-brand">
            <div class="bcos-brand-title">🇧🇷 Brazil Commerce OS</div>
            <div class="bcos-brand-sub">{escape(t['mvp'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_language = st.selectbox(
        t["language"],
        options=list(LANG_OPTIONS.keys()),
        index=list(LANG_OPTIONS.keys()).index(st.session_state.ui_language),
        key="language_selector",
    )
    if selected_language != st.session_state.ui_language:
        st.session_state.ui_language = selected_language
        st.rerun()

    module = st.radio(
        t["workspace"],
        NAV_OPTIONS,
        format_func=lambda x: t[NAV_LABEL_KEY[x]],
        key="workspace",
        label_visibility="visible",
    )

    st.markdown("---")
    st.caption(t["ai_status"])

    llm_text = t["ai_demo"] if DEMO_MODE else t["ai_live"]
    search_text = t["search_live"] if SERPER_API_KEY else t["search_offline"]
    llm_dot = "bcos-dot-amber" if DEMO_MODE else "bcos-dot-green"
    search_dot = "bcos-dot-green" if SERPER_API_KEY else "bcos-dot-amber"

    st.markdown(
        f"""
        <div class="bcos-status-row">
            <span class="bcos-chip"><span class="{llm_dot}"></span>{escape(llm_text)}</span>
            <span class="bcos-chip"><span class="{search_dot}"></span>{escape(search_text)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 00 Command Center
# =========================================================
if module == "command":
    st.markdown(
        f"""
        <div class="bcos-hero">
            <div class="bcos-kicker">AI COMMERCE AGENT</div>
            <h1>{escape(t['app_name'])}</h1>
            <p>{escape(t['tagline'])}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_header("COMMAND CENTER", t["home_title"], t["home_subtitle"])

    q = st.text_area(
        t["goal_label"],
        placeholder=t["goal_ph"],
        height=120,
        key="command_goal",
    )

    if st.button(t["route"], type="primary", key="route_request_btn"):
        if not q.strip():
            st.warning(t["empty_goal"])
        else:
            d = route_request(q)
            st.session_state["last_route"] = d.module
            save_history("Orchestrator", q[:80], f"Route → {d.module}")

    if st.session_state.get("last_route"):
        target = st.session_state["last_route"]
        nav_target = target if target in {"market", "operations", "marketing", "finance"} else "market"
        st.markdown(
            f"""
            <div class="bcos-panel">
                <div class="bcos-eyebrow">{escape(t['route_to'])}</div>
                <div class="bcos-card-title">{escape(t[NAV_LABEL_KEY[nav_target]])}</div>
                <div class="bcos-card-desc">{escape(localized_route_copy(nav_target))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            t["open_module"],
            key="open_routed_module",
            on_click=go_to_module,
            args=(nav_target,),
        )

    st.markdown("---")
    section_header("COPILOT", t["copilot"], t["copilot_sub"])
    cq = st.text_input(t["copilot_label"], placeholder=t["copilot_ph"], key="copilot_question")
    if st.button(t["ask"], key="ask_copilot_btn"):
        if not cq.strip():
            st.info(t["empty_question"])
        else:
            with st.spinner("AI…"):
                answer = chat(
                    f"{ai_lang_instruction()}\n\nUser question:\n{cq}\n\n"
                    "Answer as the Brazil Commerce OS business copilot. Be practical and concise."
                )
            st.session_state["copilot_answer"] = answer
            save_history("Copilot", cq[:80], "Answered")

    if st.session_state.get("copilot_answer"):
        st.markdown(st.session_state["copilot_answer"])


# =========================================================
# 01 Market Intelligence
# =========================================================
elif module == "market":
    mu = MARKET_UI[lang_code]

    st.markdown(
        f"""
        <div class="bcos-market-hero">
            <div class="bcos-eyebrow">{escape(mu['eyebrow'])}</div>
            <div class="title">{escape(mu['title'])}</div>
            <div class="desc">{escape(mu['subtitle'])}</div>
            <div class="bcos-feature-row">
                <span class="bcos-feature-pill">{escape(mu['feature_1'])}</span>
                <span class="bcos-feature-pill">{escape(mu['feature_2'])}</span>
                <span class="bcos-feature-pill">{escape(mu['feature_3'])}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        c1, c2 = st.columns([1, 1.35])
        with c1:
            country = st.text_input(
                mu["market"],
                value=st.session_state.get("market_country_value", "Brazil"),
                help=mu["market_help"],
                key="market_country",
            )
        with c2:
            product = st.text_input(
                mu["product"],
                placeholder=mu["product_ph"],
                key="market_product",
            )

        objective = st.text_area(
            mu["question"],
            placeholder=mu["question_ph"],
            height=96,
            key="market_objective",
        )

        with st.expander(mu["advanced"], expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                platform = st.selectbox(
                    mu["platform"],
                    ["", "Mercado Livre", "TikTok Shop", "Amazon", "Shopee", "Other / Multiple"],
                    key="market_platform",
                )
            with c2:
                price = st.text_input(
                    mu["price"],
                    placeholder=t["price_ph"],
                    key="market_price",
                )

            dims = st.multiselect(
                mu["dimensions"],
                DIMENSIONS,
                default=DIMENSIONS[:6],
                format_func=lambda x: DIMENSION_LABELS[lang_code][x],
                key="market_dimensions",
            )

        if st.button(mu["run"], type="primary", key="run_market_btn", use_container_width=True):
            if not product.strip():
                st.error(mu["need_product"])
            elif not country.strip():
                st.error(t["required"])
            else:
                selected_dims = dims or DIMENSIONS[:6]
                base_objective = objective.strip() or mu["default_objective"]
                objective_for_agent = (
                    f"{base_objective}\n\n"
                    f"OUTPUT LANGUAGE REQUIREMENT: {ai_lang_instruction()}\n"
                    "Do not translate source names or URLs."
                )
                if price.strip():
                    objective_for_agent += f"\nUSER-PROVIDED EXPECTED PRICE RANGE: {price.strip()}"

                with st.spinner(mu["spinner"]):
                    result = run_market_research(
                        country.strip(),
                        product.strip(),
                        objective_for_agent,
                        platform,
                        selected_dims,
                    )
                st.session_state.market_result = result
                st.session_state["market_last_query"] = {
                    "country": country.strip(),
                    "product": product.strip(),
                    "platform": platform,
                    "objective": base_objective,
                }
                save_history("Market", product[:80], f"{country.strip()} | {result.get('mode', '')}")

    result = st.session_state.market_result
    if result:
        live = result.get("mode") == "LIVE SEARCH"
        badge_class = "bcos-badge-live" if live else "bcos-badge-demo"
        badge_text = mu["live"] if live else mu["demo"]
        evidence = result.get("evidence") or []
        last_q = st.session_state.get("market_last_query", {})

        st.markdown(
            f"""
            <div class="bcos-report-shell">
                <div class="bcos-eyebrow">{escape(mu['report'])}</div>
                <div class="bcos-section-title">{escape(last_q.get('product', product or 'Market Research'))} · {escape(last_q.get('country', country or ''))}</div>
                <div class="bcos-section-sub">{escape(mu['report_sub'])}</div>
                <div class="bcos-report-meta">
                    <span class="{badge_class}">{escape(badge_text)}</span>
                    <span class="bcos-meta-chip">{escape(mu['evidence'])}: {len(evidence)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Full consulting-style report body
        st.markdown(result.get("analysis") or "")

        # Evidence-backed visualisations. The Market tool returns charts only
        # when comparable numeric values are supported by retrieved evidence.
        charts = result.get("charts") or []
        if charts:
            chart_heading = {
                "zh": "数据可视化",
                "en": "Evidence-backed visualisations",
                "pt-BR": "Visualizações baseadas em evidências",
            }[lang_code]
            st.markdown(f"### {chart_heading}")
            for idx, chart in enumerate(charts):
                values = chart.get("values") or []
                labels = chart.get("labels") or []
                if len(values) >= 2 and len(values) == len(labels):
                    chart_df = pd.DataFrame({
                        "label": labels,
                        "value": values,
                    }).set_index("label")
                    st.markdown(f"**{chart.get('title', 'Chart')}**")
                    if chart.get("type") == "line":
                        st.line_chart(chart_df)
                    else:
                        st.bar_chart(chart_df)
                    note_parts = []
                    if chart.get("unit"):
                        note_parts.append(str(chart.get("unit")))
                    if chart.get("source_ids"):
                        note_parts.append("Sources: " + ", ".join(chart.get("source_ids")))
                    if chart.get("note"):
                        note_parts.append(str(chart.get("note")))
                    if note_parts:
                        st.caption(" · ".join(note_parts))

        # Real deliverables: editable Word + presentation-ready PDF.
        dl_labels = {
            "zh": ("下载 Word 报告", "下载 PDF 报告", "下载 Markdown"),
            "en": ("Download Word report", "Download PDF report", "Download Markdown"),
            "pt-BR": ("Baixar relatório Word", "Baixar relatório PDF", "Baixar Markdown"),
        }[lang_code]
        filename_base = (
            f"market_research_{last_q.get('country', 'market')}_"
            f"{last_q.get('product', 'product').replace(' ', '_')[:40]}"
        )
        try:
            docx_bytes = generate_market_docx(result, lang_code)
            pdf_bytes = generate_market_pdf(result, lang_code)
            d1, d2, d3 = st.columns(3)
            d1.download_button(
                dl_labels[0],
                data=docx_bytes,
                file_name=filename_base + ".docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_market_docx",
                use_container_width=True,
            )
            d2.download_button(
                dl_labels[1],
                data=pdf_bytes,
                file_name=filename_base + ".pdf",
                mime="application/pdf",
                key="download_market_pdf",
                use_container_width=True,
            )
            d3.download_button(
                dl_labels[2],
                data=(result.get("analysis") or "").encode("utf-8"),
                file_name=filename_base + ".md",
                mime="text/markdown",
                key="download_market_md",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"Report export unavailable: {e}")

        with st.expander(mu["sources"], expanded=False):
            st.caption(mu["sources_sub"])
            if evidence:
                ev = pd.DataFrame(evidence)
                preferred = ["title", "source_type", "snippet", "link"]
                cols = [c for c in preferred if c in ev.columns] + [c for c in ev.columns if c not in preferred]
                ev = ev[cols]
                column_config = {}
                if "link" in ev.columns:
                    column_config["link"] = st.column_config.LinkColumn("URL", display_text="Open source")
                st.dataframe(
                    ev,
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config,
                )
            else:
                empty_state("No evidence returned.")


# =========================================================
# 02 E-commerce Operations
# =========================================================
elif module == "operations":
    section_header("02 · E-COMMERCE OPERATIONS", t["ops_title"], t["ops_sub"])

    st.info(t["ops_language_note"])

    # Stable IDs still exist for backend joins, but ordinary users should not
    # have to create database keys manually.
    merchant_id = ensure_internal_id("ops_merchant_internal_id", "MER")
    product_id = ensure_internal_id("ops_product_internal_id", "PRD")
    sku = ensure_internal_id("ops_sku_internal_id", "SKU")

    a, b = st.columns(2)
    product_name = a.text_input(t["product_name"], placeholder=t["product_name_ph"], key="ops_product_name")
    platform = b.selectbox(
        t["platform"],
        ["Mercado Livre", "TikTok Shop", "Amazon BR", "Shopee BR"],
        key="ops_platform",
    )

    approved_facts = st.text_area(
        t["approved_facts"],
        placeholder=t["approved_facts_ph"],
        height=130,
        key="ops_approved_facts",
    )

    a, b, c = st.columns(3)
    selling_price = a.text_input(t["selling_price"], placeholder="299", key="ops_selling_price")
    inventory = b.text_input(t["inventory"], placeholder="500", key="ops_inventory")
    unit_cost = c.text_input(t["unit_cost"], placeholder="85", key="ops_unit_cost")

    with st.expander({"zh": "内部追踪信息", "en": "Internal tracking", "pt-BR": "Rastreamento interno"}[lang_code], expanded=False):
        st.caption({
            "zh": "这些 ID 由系统自动生成，用于后续把 Operations、Marketing 和 Finance 数据关联起来；普通用户不需要手动填写。",
            "en": "These IDs are generated automatically for cross-module attribution. Users do not need to type them.",
            "pt-BR": "Esses IDs são gerados automaticamente para conectar os módulos. O usuário não precisa digitá-los.",
        }[lang_code])
        st.code(f"merchant_id={merchant_id}\nproduct_id={product_id}\nsku={sku}")

    if st.button(t["generate_launch"], type="primary", key="generate_launch_btn"):
        required = [product_name, platform, approved_facts]
        if not all(str(x).strip() for x in required):
            st.error(t["required"])
        else:
            facts_for_agent = approved_facts.strip()
            if lang_code != "pt-BR":
                facts_for_agent += (
                    "\n\nMETA INSTRUCTION (not a product fact): "
                    + ai_lang_instruction()
                    + " Keep the consumer-facing listing title, bullets and description in Brazilian Portuguese; "
                      "write checklist and warnings in the selected UI language."
                )

            with st.spinner(t["generating_launch"]):
                result = run_operations(
                    merchant_id,
                    product_id,
                    sku,
                    product_name.strip(),
                    platform,
                    facts_for_agent,
                    selling_price.strip(),
                    inventory.strip(),
                    unit_cost.strip(),
                )
            st.session_state.ops_result = result
            save_history("Operations", product_name[:80], platform)

    result = st.session_state.ops_result
    if result:
        if result.get("missing"):
            st.warning(f"{t['missing']}: " + ", ".join(result["missing"]))
        st.markdown(f"### {t['launch_pack']}")

        content = result.get("generated_pack") or ""
        st.markdown(content)

        if content.strip():
            sku_value = result.get("sku", "SKU")
            report_title = f"Launch Pack — {sku_value}"

            word_bytes = build_launch_word(report_title, content)
            pdf_bytes = build_launch_pdf(report_title, content)

            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    "Download Launch Pack (Word)",
                    data=word_bytes,
                    file_name=f"launch_pack_{sku_value}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_launch_word",
                    use_container_width=True,
                )

            with col2:
                st.download_button(
                    "Download Launch Pack (PDF)",
                    data=pdf_bytes,
                    file_name=f"launch_pack_{sku_value}.pdf",
                    mime="application/pdf",
                    key="download_launch_pdf",
                    use_container_width=True,
                )
        else:
            st.error("Launch Pack generation returned no content. Please check the LLM response before downloading.")


# =========================================================
# 03 Marketing / Creator / Content
# =========================================================
elif module == "marketing":
    section_header(
        "03 · CREATOR DISCOVERY & CAMPAIGN INTELLIGENCE",
        t["marketing_title"],
        {
            "zh": "Agent 可以自己搜索真实 Creator，也可以分析你已有的名单。先发现，再验证，再评分；不会为了凑 Top 10 编造达人。",
            "en": "The agent can discover real creators or analyse your existing list. Discover first, verify next, then score — never invent creators to fill a Top 10.",
            "pt-BR": "O agente pode descobrir creators reais ou analisar sua base existente. Primeiro descobre, depois verifica e só então pontua — sem inventar creators.",
        }[lang_code],
    )

    ui = {
        "zh": {
            "product": "产品 / 商品名称 *",
            "product_ph": "例如：90cm 猫爬架",
            "brief": "已确认的商品 / 品牌信息（选填）",
            "brief_ph": "只填写真实确认的信息，例如材料、尺寸、卖点、禁用 claims。没有也可以先留空。",
            "tracking": "内部 Campaign ID（系统自动生成）",
            "tab_discover": "AI 自动寻找 Creator",
            "tab_upload": "分析已有 Creator 名单",
            "market": "目标市场",
            "platforms": "目标平台",
            "target_n": "希望发现的候选 Creator 数量",
            "discover": "Agent 开始寻找 Creator",
            "discovering": "Agent 正在规划搜索 → 搜索真实账号 → 去重 → 检查相关性 → 必要时扩大搜索…",
            "search_plan": "Agent Search Plan",
            "search_log": "Search Execution Log",
            "candidates": "发现的真实候选 Creator",
            "pool": "Creator 数据概览",
            "creators": "Creator 数量",
            "primary": "主要数据类别",
            "fit": "与当前品类匹配度",
            "matched": "识别到的相关 Creator",
            "low": "当前 Creator 池与这个商品品类匹配度较低。系统不会为了凑 Top 10 强行推荐不相关达人。",
            "analyse": "分析 Creator 数据并生成建议",
            "no_shortlist": "未生成 Creator Shortlist：当前证据不足以支持可靠推荐。",
            "analysis": "Creator & Campaign Analysis",
            "source_note": "公开搜索找到的账号是真实来源候选，但搜索摘要不等于经过验证的粉丝量、GMV、报价或转化率。下一步应继续 enrichment / FastMoss 验证。",
            "serper_note": "AI 自动寻找需要 SERPER_API_KEY。没有 Search API 时仍可使用“分析已有 Creator 名单”。",
            "result_status": "Discovery Status",
        },
        "en": {
            "product": "Product / product name *",
            "product_ph": "Example: 90 cm cat tree",
            "brief": "Confirmed product / brand facts (optional)",
            "brief_ph": "Only confirmed facts such as materials, dimensions, selling points and prohibited claims.",
            "tracking": "Internal Campaign ID (auto-generated)",
            "tab_discover": "AI Find Creators for Me",
            "tab_upload": "Analyse My Creator List",
            "market": "Target market",
            "platforms": "Target platforms",
            "target_n": "Target number of creator candidates",
            "discover": "Agent: Discover Creators",
            "discovering": "Agent is planning searches → finding real profiles → deduplicating → checking relevance → expanding if needed…",
            "search_plan": "Agent Search Plan",
            "search_log": "Search Execution Log",
            "candidates": "Real Creator Candidates Discovered",
            "pool": "Creator dataset overview",
            "creators": "Creators",
            "primary": "Primary dataset niche",
            "fit": "Category fit",
            "matched": "Relevant creators detected",
            "low": "The current creator pool has low relevance. The system will not force an irrelevant Top 10.",
            "analyse": "Analyse Creator Data",
            "no_shortlist": "No Creator Shortlist generated: current evidence does not support a reliable recommendation.",
            "analysis": "Creator & Campaign Analysis",
            "source_note": "Public search finds real sourced profile candidates, but search snippets do not verify followers, GMV, fees or conversion. Enrichment / FastMoss verification is still required.",
            "serper_note": "Automatic discovery requires SERPER_API_KEY. Without search access, you can still use Analyse My Creator List.",
            "result_status": "Discovery Status",
        },
        "pt-BR": {
            "product": "Produto / nome do produto *",
            "product_ph": "Ex.: arranhador para gatos de 90 cm",
            "brief": "Fatos confirmados do produto / marca (opcional)",
            "brief_ph": "Informe apenas fatos confirmados: materiais, dimensões, diferenciais e claims proibidos.",
            "tracking": "Campaign ID interno (gerado automaticamente)",
            "tab_discover": "IA encontra creators",
            "tab_upload": "Analisar minha base de creators",
            "market": "Mercado-alvo",
            "platforms": "Plataformas-alvo",
            "target_n": "Número-alvo de creators candidatos",
            "discover": "Agente: descobrir creators",
            "discovering": "Agente planejando buscas → encontrando perfis reais → removendo duplicados → verificando relevância → expandindo se necessário…",
            "search_plan": "Plano de busca do agente",
            "search_log": "Log de execução da busca",
            "candidates": "Creators reais encontrados",
            "pool": "Visão geral da base de creators",
            "creators": "Creators",
            "primary": "Nicho principal da base",
            "fit": "Fit com a categoria",
            "matched": "Creators relevantes detectados",
            "low": "A base atual tem baixa relevância. O sistema não vai forçar um Top 10 irrelevante.",
            "analyse": "Analisar dados de creators",
            "no_shortlist": "Nenhuma shortlist foi gerada: as evidências atuais não sustentam uma recomendação confiável.",
            "analysis": "Análise de Creators e Campanha",
            "source_note": "A busca pública encontra candidatos reais, mas snippets não verificam seguidores, GMV, fee ou conversão. Ainda é necessário enriquecer / validar no FastMoss.",
            "serper_note": "A descoberta automática requer SERPER_API_KEY. Sem acesso à busca, ainda é possível analisar uma lista existente.",
            "result_status": "Status da descoberta",
        },
    }[lang_code]

    campaign_id = ensure_internal_id("mkt_campaign_internal_id", "CMP")

    # Shared campaign inputs for both workflows.
    product = st.text_input(
        ui["product"],
        placeholder=ui["product_ph"],
        key="mkt_product",
    )

    c1, c2, c3 = st.columns(3)
    objective = c1.selectbox(
        t["campaign_objective"],
        CAMPAIGN_OBJECTIVES,
        format_func=lambda x: CAMPAIGN_OBJECTIVE_LABELS[lang_code][x],
        key="mkt_objective",
    )
    category = c2.text_input(
        t["category"],
        placeholder=t["category_ph"],
        key="mkt_category",
    )
    budget = c3.number_input(
        t["creator_budget"],
        min_value=0.0,
        value=0.0,
        step=500.0,
        key="mkt_budget",
    )

    approved_brief = st.text_area(
        ui["brief"],
        placeholder=ui["brief_ph"],
        height=110,
        key="mkt_brief",
    )

    with st.expander(ui["tracking"], expanded=False):
        st.code(campaign_id)

    tab_discover, tab_upload = st.tabs([ui["tab_discover"], ui["tab_upload"]])

    # -------------------------------------------------------------------------
    # A) AGENTIC DISCOVERY MODE
    # -------------------------------------------------------------------------
    with tab_discover:
        d1, d2, d3 = st.columns([1, 1.5, 1])

        market = d1.text_input(
            ui["market"],
            value="Brazil",
            key="mkt_discovery_market",
        )

        platforms = d2.multiselect(
            ui["platforms"],
            ["TikTok", "Instagram", "YouTube", "Facebook", "Kwai"],
            default=["TikTok", "Instagram"],
            key="mkt_discovery_platforms",
        )

        target_count = d3.slider(
            ui["target_n"],
            min_value=5,
            max_value=50,
            value=20,
            step=5,
            key="mkt_discovery_target",
        )

        st.caption(ui["source_note"])

        if not SERPER_API_KEY:
            st.info(ui["serper_note"])

        if st.button(
            ui["discover"],
            type="primary",
            key="discover_creators_btn",
        ):
            if not product.strip() or not category.strip() or not platforms:
                st.error(t["required"])
            else:
                try:
                    with st.spinner(ui["discovering"]):
                        discovery = discover_creators(
                            product=product.strip(),
                            category=category.strip(),
                            objective=objective,
                            platforms=platforms,
                            market=market.strip() or "Brazil",
                            budget=budget if budget > 0 else None,
                            target_count=target_count,
                        )

                        candidates = discovery.get("candidates")
                        ranked = discovery.get("ranked")
                        profile = discovery.get("profile") or {}

                        brief_for_agent = (
                            (approved_brief.strip() or "No additional confirmed product facts were provided.")
                            + "\n\nMETA OUTPUT LANGUAGE: "
                            + ai_lang_instruction()
                        )

                        explanation = explain_creator_fit(
                            ranked if ranked is not None else pd.DataFrame(),
                            campaign_id,
                            product.strip(),
                            objective,
                            brief_for_agent,
                            dataset_profile=profile,
                            full_dataset=candidates if candidates is not None else pd.DataFrame(),
                            discovery_context={
                                "status": discovery.get("status"),
                                "rounds_used": discovery.get("rounds_used"),
                                "target_count": target_count,
                                "market": market,
                                "platforms": platforms,
                                "search_log": discovery.get("search_log", [])[:12],
                            },
                        )

                    st.session_state.marketing_result = {
                        "mode": "discovery",
                        "ranked": ranked.head(10) if ranked is not None else pd.DataFrame(),
                        "candidates": candidates,
                        "explanation": explanation,
                        "campaign_id": campaign_id,
                        "profile": profile,
                        "discovery": discovery,
                    }
                    save_history(
                        "Marketing",
                        product[:80],
                        f"Agent discovery | {len(candidates) if candidates is not None else 0} candidates | {discovery.get('status')}",
                    )
                except Exception as e:
                    st.error(str(e))

        current = st.session_state.get("marketing_result")
        if current and current.get("mode") == "discovery":
            discovery = current.get("discovery") or {}
            candidates = current.get("candidates")

            s1, s2, s3 = st.columns(3)
            s1.metric(ui["result_status"], discovery.get("status", "—"))
            s2.metric(
                ui["creators"],
                len(candidates) if candidates is not None else 0,
            )
            s3.metric(
                ui["matched"],
                (current.get("profile") or {}).get("matched_count", 0),
            )

            with st.expander(ui["search_plan"], expanded=False):
                st.json(discovery.get("plan", {}))

            with st.expander(ui["search_log"], expanded=False):
                log_df = pd.DataFrame(discovery.get("search_log", []))
                if not log_df.empty:
                    st.dataframe(log_df, use_container_width=True, hide_index=True)

            if candidates is not None and not candidates.empty:
                st.markdown(f"### {ui['candidates']}")
                candidate_cols = [
                    c for c in [
                        "display_name",
                        "platform",
                        "profile_url",
                        "discovery_relevance",
                        "content_focus",
                        "research_status",
                        "source",
                    ]
                    if c in candidates.columns
                ]
                st.dataframe(
                    candidates[candidate_cols] if candidate_cols else candidates,
                    use_container_width=True,
                    hide_index=True,
                )

    # -------------------------------------------------------------------------
    # B) ANALYSE EXISTING CREATOR LIST
    # -------------------------------------------------------------------------
    with tab_upload:
        creator_file = st.file_uploader(
            t["upload_creator"],
            type=["csv", "xlsx", "xls"],
            key="creator_file_uploader",
        )

        if creator_file is None:
            empty_state(
                {
                    "zh": "如果你已经有 FastMoss / agency / CRM 名单，可以上传；如果没有，请使用左侧“AI 自动寻找 Creator”。",
                    "en": "Upload a FastMoss / agency / CRM list if you already have one; otherwise use AI Find Creators for Me.",
                    "pt-BR": "Envie uma base FastMoss / agência / CRM se já tiver; caso contrário use a descoberta automática.",
                }[lang_code]
            )
        else:
            try:
                creator_df = load_creator_file(creator_file)
            except Exception as e:
                st.error(str(e))
                creator_df = None

            if creator_df is not None:
                profile = analyse_creator_dataset(
                    creator_df,
                    category.strip(),
                    product.strip(),
                )
                primary_niche = (
                    profile["top_categories"][0]["value"]
                    if profile.get("top_categories")
                    else "—"
                )
                fit_label = profile.get("fit_level", "NOT_ASSESSED")

                st.markdown(f"### {ui['pool']}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(ui["creators"], f"{profile['rows']:,}")
                m2.metric(ui["primary"], primary_niche)
                m3.metric(ui["fit"], fit_label.replace("_", " ").title())
                m4.metric(ui["matched"], f"{profile['matched_count']:,}")

                if category.strip() and not profile["can_shortlist"]:
                    st.warning(ui["low"])

                preview_cols = [
                    c for c in [
                        "display_name", "followers", "category", "platform",
                        "profile_url", "content_focus", "research_status",
                    ]
                    if c in creator_df.columns
                ]
                preview = (
                    creator_df[preview_cols].head(30)
                    if preview_cols
                    else creator_df.head(30)
                )
                st.dataframe(preview, use_container_width=True, hide_index=True)

                if st.button(
                    ui["analyse"],
                    type="primary",
                    key="build_shortlist_btn",
                ):
                    if not product.strip() or not category.strip():
                        st.error(t["required"])
                    else:
                        ranked = score_creators(
                            creator_df,
                            category.strip(),
                            budget if budget > 0 else None,
                            product=product.strip(),
                        )
                        profile = ranked.attrs.get("dataset_profile", profile)

                        brief_for_agent = (
                            (approved_brief.strip() or "No additional confirmed product facts were provided.")
                            + "\n\nMETA OUTPUT LANGUAGE: "
                            + ai_lang_instruction()
                        )

                        with st.spinner(t["analysing_fit"]):
                            explanation = explain_creator_fit(
                                ranked,
                                campaign_id,
                                product.strip(),
                                objective,
                                brief_for_agent,
                                dataset_profile=profile,
                                full_dataset=creator_df,
                                discovery_context={
                                    "mode": "user_uploaded_creator_list",
                                    "filename": creator_file.name,
                                    "rows": len(creator_df),
                                },
                            )

                        st.session_state.marketing_result = {
                            "mode": "upload",
                            "ranked": ranked.head(10),
                            "explanation": explanation,
                            "campaign_id": campaign_id,
                            "profile": profile,
                        }

                        save_history(
                            "Marketing",
                            product[:80],
                            f"{len(creator_df)} creators | fit={profile.get('fit_level')}",
                        )

    # -------------------------------------------------------------------------
    # SHARED DECISION OUTPUT
    # -------------------------------------------------------------------------
    result = st.session_state.marketing_result

    if result:
        ranked = result.get("ranked")

        if ranked is not None and not ranked.empty:
            st.markdown(
                {
                    "zh": "### 推荐 Creator Shortlist",
                    "en": "### Recommended Creator Shortlist",
                    "pt-BR": "### Shortlist recomendada de creators",
                }[lang_code]
            )

            show_cols = [
                c for c in [
                    "display_name",
                    "platform",
                    "category",
                    "followers",
                    "avg_views",
                    "engagement_rate",
                    "gmv_30d",
                    "fee_brl",
                    "fit_score",
                    "data_confidence",
                    "profile_url",
                    "research_status",
                ]
                if c in ranked.columns
            ]

            st.dataframe(
                ranked[show_cols] if show_cols else ranked,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(ui["no_shortlist"])

        st.markdown(f"### {ui['analysis']}")
        analysis_text = result.get("explanation") or ""
        st.markdown(analysis_text)

        if analysis_text.strip():
            report_title = f"Creator & Campaign Analysis — {result.get('campaign_id', 'campaign')}"
            word_bytes = build_launch_word(report_title, analysis_text)
            pdf_bytes = build_launch_pdf(report_title, analysis_text)

            dl1, dl2 = st.columns(2)

            with dl1:
                st.download_button(
                    "Download Creator Analysis (Word)",
                    data=word_bytes,
                    file_name=f"creator_analysis_{result.get('campaign_id', 'campaign')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_creator_analysis_word",
                    use_container_width=True,
                )

            with dl2:
                st.download_button(
                    "Download Creator Analysis (PDF)",
                    data=pdf_bytes,
                    file_name=f"creator_analysis_{result.get('campaign_id', 'campaign')}.pdf",
                    mime="application/pdf",
                    key="download_creator_analysis_pdf",
                    use_container_width=True,
                )

    template_bytes = safe_template_bytes(BASE / "data" / "creator_sample.csv")
    if template_bytes is not None:
        st.download_button(
            t["download_creator_template"],
            data=template_bytes,
            file_name="creator_sample.csv",
            mime="text/csv",
            key="download_creator_template",
        )


# =========================================================
# 04 Finance & Performance
# =========================================================
elif module == "finance":
    from tools.finance_workspace import render_finance
    render_finance(BASE, ai_lang_instruction(), build_launch_word, build_launch_pdf, save_history)


# =========================================================
# Audit Trail
# =========================================================
elif module == "audit":
    section_header("AUDIT", t["audit_title"], t["audit_sub"])

    if not st.session_state.history:
        empty_state(t["no_history"])
    else:
        st.dataframe(
            pd.DataFrame(st.session_state.history),
            use_container_width=True,
            hide_index=True,
        )
        if st.button(t["clear_history"], key="clear_history_btn"):
            st.session_state.history = []
            st.success(t["history_cleared"])
            st.rerun()
