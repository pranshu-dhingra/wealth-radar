"""generate_documents.py — Creates 5 sample PDF documents for WealthRadar demo.

Documents are stored in backend/app/data/documents/.
Each is mapped to a client_id from clients.json.

Client mappings:
  johnson_trust.pdf           -> CLT001  Mark Johnson     (Tier A, age 77, RMD-eligible)
  smith_account_statement.pdf -> CLT002  Julia Nelson     (Tier A, age 74, portfolio drift)
  davis_tax_return_summary.pdf-> CLT005  Adam Howell      (Tier A, age 62, TLH + estate)
  wilson_insurance_policy.pdf -> CLT013  Timothy Kane     (Tier B, age 66)
  martinez_estate_plan.pdf    -> CLT040  Carol Martinez   (Tier D, age 69, widowed)
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).parent.parent / "backend" / "app" / "data" / "documents"

NAVY = colors.HexColor("#1a3a5c")
LIGHT_BLUE = colors.HexColor("#e8f0fe")
ROW_ALT = colors.HexColor("#f0f4f8")
ROW_ALT2 = colors.HexColor("#f8f9fa")
RED = colors.HexColor("#c0392b")
ORANGE = colors.HexColor("#e67e22")
BLUE = colors.HexColor("#2980b9")
GREEN = colors.HexColor("#27ae60")


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def make_styles():
    styles = getSampleStyleSheet()
    defs = [
        ParagraphStyle("DocTitle",    fontSize=16, fontName="Helvetica-Bold",
                       spaceAfter=4, alignment=TA_CENTER),
        ParagraphStyle("DocSubtitle", fontSize=10, fontName="Helvetica",
                       spaceAfter=10, alignment=TA_CENTER, textColor=colors.grey),
        ParagraphStyle("Section",     fontSize=10, fontName="Helvetica-Bold",
                       spaceBefore=10, spaceAfter=3, textColor=NAVY),
        ParagraphStyle("Body",        fontSize=9,  fontName="Helvetica",
                       spaceAfter=4, leading=13),
        ParagraphStyle("Small",       fontSize=7.5, fontName="Helvetica",
                       textColor=colors.grey),
        ParagraphStyle("Footer",      fontSize=7.5, fontName="Helvetica",
                       textColor=colors.grey, alignment=TA_CENTER),
    ]
    for s in defs:
        styles.add(s)
    return styles


def _header(story, title, subtitle, client_id, doc_id, styles):
    story.append(Paragraph(title, styles["DocTitle"]))
    story.append(Paragraph(subtitle, styles["DocSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=NAVY))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(
        f"<i>WealthRadar Client ID: {client_id} &nbsp;·&nbsp; "
        f"Document ID: {doc_id}</i>", styles["Small"]))
    story.append(Spacer(1, 0.1 * inch))


def _footer(story, disclaimer, styles):
    story.append(Spacer(1, 0.15 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 0.04 * inch))
    story.append(Paragraph(
        disclaimer + "  This document is a synthetic example generated for "
        "WealthRadar demo purposes. NOT a real legal or financial document.",
        styles["Footer"]))


def _table_style(header_cols=None, bold_last=False, align_right_from=None):
    """Return a base TableStyle with navy header row."""
    cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT2]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("PADDING",     (0, 0), (-1, -1), 4),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]
    if header_cols:
        for col in header_cols:
            cmds.append(("FONTNAME", (col, 1), (col, -1), "Helvetica-Bold"))
    if bold_last:
        cmds += [
            ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
        ]
    if align_right_from is not None:
        cmds.append(("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"))
    return TableStyle(cmds)


# ---------------------------------------------------------------------------
# 1. johnson_trust.pdf  — CLT001  Mark Johnson  (Tier A, age 77, RMD-eligible)
# ---------------------------------------------------------------------------

def generate_johnson_trust(styles):
    path = OUT_DIR / "johnson_trust.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            leftMargin=1 * inch, rightMargin=1 * inch)
    story = []

    _header(story,
            "THE MARK A. JOHNSON REVOCABLE LIVING TRUST",
            "Established January 15, 2019  ·  Last Amended October 3, 2022",
            "CLT001", "DOC-TRU-001", styles)

    # --- Article I ---
    story.append(Paragraph("ARTICLE I — DECLARATION OF TRUST", styles["Section"]))
    story.append(Paragraph(
        "I, <b>MARK ALAN JOHNSON</b>, residing at 4821 Ridgecrest Drive, Greenwich, CT 06830 "
        "(the \"Grantor\" and initial \"Trustee\"), hereby transfer to myself as Trustee, or to my "
        "Successor Trustee, all property listed in Schedule A, to be held, administered, and "
        "distributed in accordance with this trust instrument. This trust shall be known as "
        "<b>The Mark A. Johnson Revocable Living Trust</b>, dated January 15, 2019.",
        styles["Body"]))

    # --- Trustees table ---
    story.append(Paragraph("ARTICLE II — TRUSTEES", styles["Section"]))
    t_data = [
        ["Role", "Name", "Relationship", "Address"],
        ["Primary Trustee",    "Mark Alan Johnson",      "Grantor",     "4821 Ridgecrest Dr, Greenwich CT 06830"],
        ["Successor Trustee",  "Patricia Lynn Johnson",  "Spouse",      "4821 Ridgecrest Dr, Greenwich CT 06830"],
        ["Successor Trustee",  "Daniel M. Johnson",      "Son",         "112 Maple Ave, Boston MA 02101"],
        ["Co-Trustee (Alt.)",  "First Republic Trust Co.", "Institution", "Hartford CT 06103"],
    ]
    t = Table(t_data, colWidths=[1.15 * inch, 1.6 * inch, 1.15 * inch, 2.6 * inch])
    t.setStyle(_table_style())
    story.append(t)

    # --- Beneficiaries table ---
    story.append(Paragraph("ARTICLE III — BENEFICIARIES", styles["Section"]))
    b_data = [
        ["Beneficiary",            "Relationship", "Share",          "Condition"],
        ["Patricia Lynn Johnson",  "Spouse",       "100% (primary)", "Surviving spouse"],
        ["Daniel M. Johnson",      "Son",          "50% contingent", "If spouse predeceases"],
        ["Sarah E. Johnson-Park",  "Daughter",     "50% contingent", "If spouse predeceases"],
        ["Johnson Family Foundation", "Charitable","10% of residue", "Per Schedule B"],
    ]
    t2 = Table(b_data, colWidths=[1.7 * inch, 1.2 * inch, 1.4 * inch, 2.25 * inch])
    t2.setStyle(_table_style())
    story.append(t2)

    # --- Distribution provisions ---
    story.append(Paragraph("ARTICLE IV — DISTRIBUTION PROVISIONS", styles["Section"]))
    provs = [
        ("<b>4.1 During Grantor's Lifetime:</b> The Trustee shall distribute to the Grantor "
         "such income and principal as the Grantor directs in writing, or as the Trustee "
         "determines necessary for the Grantor's health, education, maintenance, and support."),
        ("<b>4.2 Upon Grantor's Incapacity:</b> The Successor Trustee shall manage trust "
         "assets and make distributions for the Grantor's care and the support of the "
         "Grantor's spouse. Annual distributions shall not exceed $180,000 without court approval."),
        ("<b>4.3 Upon Grantor's Death:</b> After payment of debts and expenses, the Trustee "
         "shall distribute the residuary estate per Article III. Required Minimum Distributions "
         "from inherited IRA accounts shall be calculated per IRS Pub. 590-B, Uniform Lifetime "
         "Table III, using the Successor Beneficiary's age in the year of distribution."),
        ("<b>4.4 Charitable Remainder:</b> Per Schedule B, 10% of the net residuary estate "
         "shall be transferred to the Johnson Family Foundation (EIN 46-XXXXXXX), a 501(c)(3) "
         "organization, within 12 months of the Grantor's death."),
    ]
    for p in provs:
        story.append(Paragraph(p, styles["Body"]))

    # --- Key dates ---
    story.append(Paragraph("KEY DATES & AMENDMENTS", styles["Section"]))
    d_data = [
        ["Event",                                "Date",             "Attorney / Notary"],
        ["Trust Established",                    "Jan 15, 2019",     "Whitmore & Callahan LLP, Greenwich CT"],
        ["Amendment No. 1 (beneficiary update)", "Mar 22, 2021",     "Whitmore & Callahan LLP"],
        ["Amendment No. 2 (charitable provision)","Oct 3, 2022",     "Whitmore & Callahan LLP"],
        ["Last advisor review",                  "Nov 14, 2024",     "WealthRadar Compliance"],
    ]
    t3 = Table(d_data, colWidths=[2.2 * inch, 1.4 * inch, 2.95 * inch])
    t3.setStyle(_table_style())
    story.append(t3)

    # --- Page 2 ---
    story.append(PageBreak())
    story.append(Paragraph("ARTICLE V — AMENDMENT AND REVOCATION", styles["Section"]))
    story.append(Paragraph(
        "During the Grantor's lifetime and while the Grantor retains legal capacity, this trust "
        "may be amended or revoked in whole or in part by a written instrument signed by the "
        "Grantor and delivered to the Trustee. Upon the Grantor's death or adjudicated "
        "incapacity, this trust shall become irrevocable.", styles["Body"]))

    story.append(Paragraph("ARTICLE VI — TRUSTEE POWERS", styles["Section"]))
    powers = [
        "Invest and reinvest trust assets in any property, including stocks, bonds, mutual funds, and ETFs;",
        "Sell, exchange, or otherwise dispose of trust property at public or private sale;",
        "Collect income and principal and give receipts and discharges therefor;",
        "Exercise voting rights and other rights appurtenant to securities held in trust;",
        "Make distributions in cash or in kind, or partly in each, at values determined by the Trustee;",
        "Employ and compensate investment advisors, attorneys, accountants, and other agents;",
        "Make, execute, and deliver deeds, assignments, and other instruments to carry out trust purposes.",
    ]
    for i, p in enumerate(powers, 1):
        story.append(Paragraph(f"{i}. {p}", styles["Body"]))

    story.append(Paragraph("SCHEDULE A — TRUST PROPERTY (as of December 31, 2024)", styles["Section"]))
    sa_data = [
        ["Asset",                    "Account / Description",               "Approx. Value"],
        ["Traditional IRA",          "Fidelity Acct #XXXX-7821",            "$1,240,000"],
        ["Roth IRA",                 "Fidelity Acct #XXXX-7822",            "$380,000"],
        ["Trust Brokerage",          "Merrill Lynch Acct #XXXX-4490",       "$920,000"],
        ["Real Property",            "4821 Ridgecrest Dr, Greenwich CT",    "$1,850,000"],
        ["Life Insurance (CSV)",     "MetLife Policy #ML-XXXXXX",           "$142,000"],
        ["",                         "TOTAL ESTIMATED TRUST ASSETS",        "$4,532,000"],
    ]
    t4 = Table(sa_data, colWidths=[1.75 * inch, 2.7 * inch, 2.1 * inch])
    style4 = _table_style(align_right_from=2, bold_last=True)
    t4.setStyle(style4)
    story.append(t4)

    _footer(story,
            "This trust summary is prepared for advisor planning purposes and does not constitute legal advice.",
            styles)
    doc.build(story)
    print(f"  Created: {path.name}  (CLT001 Mark Johnson)")
    return path


# ---------------------------------------------------------------------------
# 2. smith_account_statement.pdf  — CLT002  (Tier A, age 74, portfolio drift)
# ---------------------------------------------------------------------------

def generate_smith_account_statement(styles):
    path = OUT_DIR / "smith_account_statement.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch)
    story = []

    _header(story,
            "MERIDIAN WEALTH MANAGEMENT",
            "Quarterly Account Statement  ·  Q4 2025  (October 1 – December 31, 2025)",
            "CLT002", "DOC-STM-001", styles)

    # Account info
    acct_data = [
        ["Account Holder:", "Robert T. Smith",           "Statement Period:", "Oct 1 – Dec 31, 2025"],
        ["Client ID:",       "CLT002",                    "Account Number:",   "MWM-XXXX-4821"],
        ["Account Type:",    "Traditional IRA",           "Tax Year:",         "2025"],
        ["Advisor:",         "Jennifer Walsh, CFP(r)",   "Statement Date:",   "January 12, 2026"],
    ]
    ta = Table(acct_data, colWidths=[1.2 * inch, 2.1 * inch, 1.35 * inch, 2.2 * inch])
    ta.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, -1), ROW_ALT),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("PADDING",    (0, 0), (-1, -1), 5),
    ]))
    story.append(ta)
    story.append(Spacer(1, 0.1 * inch))

    # Account summary
    story.append(Paragraph("ACCOUNT SUMMARY", styles["Section"]))
    sum_data = [
        ["",                              "This Quarter",    "Prior Quarter",   "Year-to-Date"],
        ["Beginning Value",               "$1,842,310",      "$1,798,450",       "$1,720,680"],
        ["Contributions / Deposits",      "$0",              "$0",               "$0"],
        ["Withdrawals / Distributions",   "($48,200)",       "$0",               "($48,200)"],
        ["Investment Gain / (Loss)",      "$38,140",         "$43,860",          "$111,770"],
        ["Advisory Fees",                 "($4,608)",        "($4,496)",         "($18,130)"],
        ["Ending Value",                  "$1,827,642",      "$1,842,310",       "$1,827,642"],
        ["Quarterly Return",              "+1.84%",          "+2.44%",           "+6.22% YTD"],
    ]
    ts = Table(sum_data, colWidths=[2.15 * inch, 1.7 * inch, 1.7 * inch, 1.7 * inch])
    ts.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",    (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",    (0, -2), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND",  (0, -2), (-1, -1), LIGHT_BLUE),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -3), [colors.white, ROW_ALT2]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ALIGN",       (1, 0), (-1, -1), "RIGHT"),
        ("PADDING",     (0, 0), (-1, -1), 4),
    ]))
    story.append(ts)
    story.append(Spacer(1, 0.06 * inch))
    story.append(Paragraph(
        "<b>Advisor Alert:</b> Portfolio drift detected. US Equity is currently 68.4% vs. "
        "target 60.0% (+8.4% drift). Rebalancing recommended per IPS guidelines.",
        styles["Body"]))

    # Holdings table
    story.append(Paragraph("HOLDINGS AS OF DECEMBER 31, 2025", styles["Section"]))
    h_data = [
        ["Ticker", "Description",               "Asset Class",  "Shares",  "Price",    "Mkt Value", "Wt%",    "Gain/Loss"],
        ["VTI",    "Vanguard Total Stock Mkt",  "US Equity",    "2,841",   "$289.40",  "$821,865",  "44.97%", "+$142,310"],
        ["QQQ",    "Invesco Nasdaq 100",         "US Equity",    "580",     "$492.10",  "$285,418",  "15.62%", "+$48,220"],
        ["SCHD",   "Schwab US Dividend Equity",  "US Equity",    "1,240",   "$87.30",   "$108,252",  "5.93%",  "+$18,640"],
        ["VXUS",   "Vanguard Total Intl Stock",  "Intl Equity",  "1,820",   "$62.80",   "$114,296",  "6.26%",  "+$8,410"],
        ["IEMG",   "iShares Core MSCI EM",       "Intl Equity",  "920",     "$48.20",   "$44,344",   "2.43%",  "-$3,210"],
        ["BND",    "Vanguard Total Bond Mkt",     "US Bond",      "1,650",   "$72.40",   "$119,460",  "6.54%",  "+$2,890"],
        ["AGG",    "iShares Core US Agg Bond",   "US Bond",      "880",     "$95.80",   "$84,304",   "4.62%",  "+$1,240"],
        ["BNDX",   "Vanguard Total Intl Bond",   "Intl Bond",    "960",     "$49.60",   "$47,616",   "2.61%",  "+$890"],
        ["VNQ",    "Vanguard Real Estate ETF",   "Real Estate",  "520",     "$84.20",   "$43,784",   "2.40%",  "-$1,820"],
        ["GLD",    "SPDR Gold Shares",            "Commodities",  "210",     "$196.40",  "$41,244",   "2.26%",  "+$6,110"],
        ["Cash",   "Money Market",               "Cash",         "—",       "—",        "$86,467",   "4.73%",  "—"],
        ["TOTAL",  "",                           "",             "",        "",         "$1,827,642","100.00%","+$224,020"],
    ]
    col_w = [0.55, 1.65, 0.88, 0.55, 0.65, 0.85, 0.58, 0.72]
    th = Table(h_data, colWidths=[w * inch for w in col_w])
    th.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND",  (0, -1), (-1, -1), LIGHT_BLUE),
        ("FONTSIZE",    (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, ROW_ALT2]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ALIGN",       (3, 0), (-1, -1), "RIGHT"),
        ("PADDING",     (0, 0), (-1, -1), 3),
    ]))
    story.append(th)

    # Allocation vs target
    story.append(Paragraph("ASSET ALLOCATION vs. TARGET IPS", styles["Section"]))
    al_data = [
        ["Asset Class",       "Current %", "Target %", "Drift",   "Status"],
        ["US Equity",         "68.40%",    "60.00%",   "+8.40%",  "REBALANCE"],
        ["Intl Equity",       "8.69%",     "15.00%",   "-6.31%",  "REBALANCE"],
        ["US Bond",           "12.83%",    "15.00%",   "-2.17%",  "OK"],
        ["Intl Bond",         "2.61%",     "5.00%",    "-2.39%",  "OK"],
        ["Real Estate",       "2.40%",     "3.00%",    "-0.60%",  "OK"],
        ["Commodities",       "2.26%",     "2.00%",    "+0.26%",  "OK"],
        ["Cash",              "4.73%",     "0.00%",    "+4.73%",  "Deploy"],
    ]
    tal = Table(al_data, colWidths=[1.75 * inch, 1.0 * inch, 1.0 * inch, 0.9 * inch, 1.2 * inch])
    tal.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT2]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
        ("PADDING",     (0, 0), (-1, -1), 4),
        ("TEXTCOLOR",   (4, 1), (4, 2), RED),
        ("FONTNAME",    (4, 1), (4, 2), "Helvetica-Bold"),
    ]))
    story.append(tal)

    # Fees
    story.append(Paragraph("ADVISORY FEES", styles["Section"]))
    fee_data = [
        ["Fee Type",                  "Rate",        "Q4 2025",    "YTD 2025"],
        ["Investment Advisory Fee",   "1.00% AUM",   "$4,608",     "$18,130"],
        ["Custodian Fee (Fidelity)",  "Waived",      "$0",         "$0"],
        ["Total Fees",                "",            "$4,608",     "$18,130"],
    ]
    tf = Table(fee_data, colWidths=[2.3 * inch, 1.1 * inch, 1.3 * inch, 1.3 * inch])
    tf.setStyle(_table_style(bold_last=True, align_right_from=2))
    story.append(tf)

    _footer(story,
            "This statement is for informational purposes only. Past performance is not indicative of future results.",
            styles)
    doc.build(story)
    print(f"  Created: {path.name}  (CLT002 — Tier A, portfolio drift)")
    return path


# ---------------------------------------------------------------------------
# 3. davis_tax_return_summary.pdf  — CLT005  (Tier A, age 62, TLH, estate)
# ---------------------------------------------------------------------------

def generate_davis_tax_return(styles):
    path = OUT_DIR / "davis_tax_return_summary.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            leftMargin=1 * inch, rightMargin=1 * inch)
    story = []

    _header(story,
            "2025 FEDERAL TAX RETURN SUMMARY",
            "Form 1040 — Individual Income Tax Return (Advisor Extract)",
            "CLT005", "DOC-TAX-001", styles)

    # Taxpayer info
    story.append(Paragraph("TAXPAYER INFORMATION", styles["Section"]))
    tp_data = [
        ["Primary Taxpayer:", "Michael R. Davis",              "SSN:",   "XXX-XX-4821"],
        ["Spouse:",           "Sandra K. Davis",               "SSN:",   "XXX-XX-7302"],
        ["Filing Status:",    "Married Filing Jointly",        "Tax Year:", "2025"],
        ["Address:",          "2240 Fairway Lane, Austin TX 78746", "CPA:", "Bernstein & Okafor CPA"],
    ]
    tt = Table(tp_data, colWidths=[1.35 * inch, 2.15 * inch, 0.75 * inch, 2.25 * inch])
    tt.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, -1), ROW_ALT),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("PADDING",    (0, 0), (-1, -1), 4),
    ]))
    story.append(tt)

    # Income summary
    story.append(Paragraph("INCOME SUMMARY  (Form 1040, Lines 1–11)", styles["Section"]))
    inc_data = [
        ["Income Source",                              "Amount",     "Form"],
        ["W-2 Wages & Salaries (Primary)",             "$285,000",   "W-2"],
        ["W-2 Wages & Salaries (Spouse)",              "$0",         "W-2"],
        ["Business Income (Schedule C)",               "$48,200",    "Sch C"],
        ["Ordinary Dividends",                         "$12,840",    "1099-DIV"],
        ["  Qualified Dividends (subset)",             "($9,210)",   "1099-DIV"],
        ["Long-Term Capital Gains",                    "$31,450",    "1099-B / Sch D"],
        ["Short-Term Capital Gains",                   "$4,820",     "1099-B / Sch D"],
        ["IRA Distributions (Traditional)",            "$0",         "1099-R"],
        ["Interest Income",                            "$3,280",     "1099-INT"],
        ["Other Income",                               "$2,100",     "Various"],
        ["GROSS INCOME",                               "$387,690",   ""],
        ["Adjustments (IRA Deduction, HSA, etc.)",     "($8,400)",   ""],
        ["ADJUSTED GROSS INCOME (AGI)",                "$379,290",   "1040 Line 11"],
    ]
    ti = Table(inc_data, colWidths=[3.3 * inch, 1.5 * inch, 1.7 * inch])
    ti.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT2]),
        ("FONTNAME",    (0, 12), (-1, 12), "Helvetica-Bold"),
        ("FONTNAME",    (0, 14), (-1, 14), "Helvetica-Bold"),
        ("BACKGROUND",  (0, 14), (-1, 14), LIGHT_BLUE),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("PADDING",     (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 5), (0, 5), 16),   # indent qualified div sub-item
    ]))
    story.append(ti)

    # Deductions & tax
    story.append(Paragraph("DEDUCTIONS & TAX CALCULATION", styles["Section"]))
    tax_data = [
        ["Item",                                             "Amount"],
        ["AGI",                                              "$379,290"],
        ["Itemized Deductions (Schedule A)",                 "($48,320)"],
        ["  Mortgage Interest",                              "($18,400)"],
        ["  State & Local Taxes (SALT cap)",                 "($10,000)"],
        ["  Charitable Contributions",                       "($12,800)"],
        ["  Other Itemized",                                 "($7,120)"],
        ["Qualified Business Income Deduction (Sec. 199A)", "($9,640)"],
        ["TAXABLE INCOME",                                   "$321,330"],
        ["Federal Income Tax (brackets)",                    "$80,182"],
        ["LTCG / Qualified Dividend Tax",                    "$4,718"],
        ["Self-Employment Tax",                              "$6,824"],
        ["Net Investment Income Tax (3.8%)",                 "$2,890"],
        ["TOTAL TAX BEFORE CREDITS",                         "$94,614"],
        ["Credits (Child Tax, Energy Efficiency)",           "($4,200)"],
        ["TOTAL FEDERAL TAX LIABILITY",                      "$90,414"],
        ["Federal Withholding & Est. Payments",              "($95,000)"],
        ["REFUND",                                           "$4,586"],
    ]
    td = Table(tax_data, colWidths=[3.7 * inch, 2.8 * inch])
    td.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT2]),
        ("FONTNAME",    (0, 9), (-1, 9), "Helvetica-Bold"),
        ("BACKGROUND",  (0, 9), (-1, 9), LIGHT_BLUE),
        ("FONTNAME",    (0, 14), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND",  (0, -1), (-1, -1), colors.HexColor("#e8f4e8")),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("PADDING",     (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 3), (0, 7), 16),
    ]))
    story.append(td)

    # Advisor notes
    story.append(Paragraph("ADVISOR PLANNING NOTES", styles["Section"]))
    story.append(Paragraph(
        "<b>Tax-Loss Harvesting (2026):</b> Client holds unrealized losses of ~$18,400 in "
        "taxable brokerage (IEMG: -$8,200; BND: -$4,100; QQQ: -$6,100). Recommend harvesting "
        "Q1 2026. Observe 61-day wash-sale window per IRC Sec. 1091.",
        styles["Body"]))
    story.append(Paragraph(
        "<b>Roth Conversion Window:</b> Client is in the 32% bracket (AGI $379K vs. $383,900 "
        "ceiling). Partial conversion of $50K–$80K may be advantageous if 2026 income is lower "
        "due to business income variability. Coordinate with CPA before April 15, 2026.",
        styles["Body"]))
    story.append(Paragraph(
        "<b>Effective Rate:</b> $90,414 / $379,290 AGI = 23.8% effective federal rate. "
        "Marginal rate: 32% + 3.8% NIIT on net investment income.",
        styles["Body"]))

    _footer(story,
            "This is an advisor extract for planning use only — not a copy of the filed return.",
            styles)
    doc.build(story)
    print(f"  Created: {path.name}  (CLT005 — Tier A, TLH opportunity)")
    return path


# ---------------------------------------------------------------------------
# 4. wilson_insurance_policy.pdf  — CLT013  Timothy Kane  (Tier B, age 66)
# ---------------------------------------------------------------------------

def generate_wilson_insurance(styles):
    path = OUT_DIR / "wilson_insurance_policy.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            leftMargin=1 * inch, rightMargin=1 * inch)
    story = []

    _header(story,
            "LIFE INSURANCE POLICY SUMMARY",
            "Nationwide Life and Annuity Insurance Company",
            "CLT013", "DOC-INS-001", styles)

    # Policy overview
    story.append(Paragraph("POLICY OVERVIEW", styles["Section"]))
    po_data = [
        ["Policy Number:",    "NWL-XXXXXXX-2019",    "Issue Date:",              "March 15, 2019"],
        ["Policy Type:",      "Universal Life (UL)",  "Policy Status:",           "In Force"],
        ["Insured:",          "James R. Wilson",      "Date of Birth:",           "Aug 22, 1959 (Age 66)"],
        ["Owner:",            "James R. Wilson",      "Primary Beneficiary:",     "Margaret A. Wilson (Spouse)"],
        ["State of Issue:",   "Georgia",              "Contingent Beneficiary:",  "Wilson Family Trust"],
    ]
    tp = Table(po_data, colWidths=[1.4 * inch, 1.85 * inch, 1.55 * inch, 1.85 * inch])
    tp.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, -1), ROW_ALT),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("PADDING",    (0, 0), (-1, -1), 5),
    ]))
    story.append(tp)

    # Coverage
    story.append(Paragraph("COVERAGE & DEATH BENEFIT", styles["Section"]))
    db_data = [
        ["Component",                        "Amount / Detail"],
        ["Base Death Benefit",               "$1,500,000"],
        ["Death Benefit Option",             "Option B (Increasing)  —  DB = Face + Cash Value"],
        ["Current Total Death Benefit (est.)","$1,682,400"],
        ["Accelerated Death Benefit Rider",  "Included — terminal illness (12 months or less)"],
        ["Waiver of Premium Rider",          "Included — disability after 6-month elimination period"],
        ["Long-Term Care Rider",             "Not elected"],
        ["Guaranteed Insurability Rider",    "Expired per policy terms at age 50"],
    ]
    tdb = Table(db_data, colWidths=[2.75 * inch, 3.75 * inch])
    tdb.setStyle(_table_style(header_cols=[0]))
    story.append(tdb)

    # Premium & cash value
    story.append(Paragraph("PREMIUM & CASH VALUE  (Annual, 2025)", styles["Section"]))
    cv_data = [
        ["Item",                              "Annual",    "Monthly",  "YTD 2025"],
        ["Scheduled Premium",                 "$18,400",   "$1,533",   "$18,400"],
        ["Cost of Insurance (COI)",           "($4,820)",  "($402)",   "($4,820)"],
        ["Policy Expense Charge",             "($480)",    "($40)",    "($480)"],
        ["Net Credited to Cash Value",        "$13,100",   "$1,092",   "$13,100"],
        ["Current Crediting Rate (Indexed)",  "5.80%",     "—",        "—"],
        ["Guaranteed Minimum Rate",           "2.00%",     "—",        "—"],
    ]
    tcv = Table(cv_data, colWidths=[2.6 * inch, 1.25 * inch, 1.15 * inch, 1.5 * inch])
    tcv.setStyle(_table_style(header_cols=[0], align_right_from=1))
    story.append(tcv)

    # Cash value history
    story.append(Paragraph("CASH VALUE HISTORY", styles["Section"]))
    hist_data = [
        ["Date",              "Premiums Paid", "Cash Value", "Surrender Value", "Death Benefit"],
        ["Dec 31, 2021",      "$36,800",       "$88,420",    "$78,220",          "$1,588,420"],
        ["Dec 31, 2022",      "$55,200",       "$108,640",   "$101,440",         "$1,608,640"],
        ["Dec 31, 2023",      "$73,600",       "$134,280",   "$129,280",         "$1,634,280"],
        ["Dec 31, 2024",      "$92,000",       "$169,110",   "$165,110",         "$1,669,110"],
        ["Jan 1, 2026",       "$110,400",      "$182,400",   "$178,900",         "$1,682,400"],
    ]
    th2 = Table(hist_data, colWidths=[1.35 * inch, 1.3 * inch, 1.25 * inch, 1.35 * inch, 1.3 * inch])
    th2.setStyle(_table_style(bold_last=True, align_right_from=1))
    story.append(th2)

    # Planning notes
    story.append(Paragraph("ADVISOR PLANNING NOTES", styles["Section"]))
    story.append(Paragraph(
        "<b>Beneficiary Review — URGENT:</b> Primary beneficiary (Margaret A. Wilson) was "
        "designated in 2019. Per advisor records, client and spouse separated in 2024. "
        "Recommend immediate beneficiary update. ERISA does not govern life insurance; "
        "Georgia state law (O.C.G.A. Sec. 33-25-1) controls designation.",
        styles["Body"]))
    story.append(Paragraph(
        "<b>Policy Exchange Consideration (Sec. 1035):</b> At age 66, COI charges on "
        "Universal Life will escalate significantly. A Sec. 1035 tax-free exchange to a "
        "Guaranteed UL or Whole Life product may provide better cost certainty. "
        "Request an in-force illustration and comparison from Nationwide.",
        styles["Body"]))
    story.append(Paragraph(
        "<b>Estate Planning Interaction:</b> Death benefit ($1,682,400) is currently included "
        "in client's taxable estate. Consider transferring ownership to an Irrevocable Life "
        "Insurance Trust (ILIT) to exclude proceeds from estate per IRC Sec. 2042.",
        styles["Body"]))

    _footer(story,
            "This summary is prepared for advisor planning use only. Refer to the original policy contract for binding terms.",
            styles)
    doc.build(story)
    print(f"  Created: {path.name}  (CLT013 — Tier B, age 66)")
    return path


# ---------------------------------------------------------------------------
# 5. martinez_estate_plan.pdf  — CLT040  Carol Martinez  (Tier D, age 69, widowed)
# ---------------------------------------------------------------------------

def generate_martinez_estate_plan(styles):
    path = OUT_DIR / "martinez_estate_plan.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch)
    story = []

    _header(story,
            "ESTATE PLANNING CHECKLIST & STATUS REPORT",
            "Annual Advisor Review  ·  February 15, 2026",
            "CLT040", "DOC-EST-001", styles)

    # Client profile
    story.append(Paragraph("CLIENT PROFILE", styles["Section"]))
    cp_data = [
        ["Client Name:",      "Carol E. Martinez",                  "Date of Birth:",    "July 14, 1956 (Age 69)"],
        ["Marital Status:",   "Widowed (spouse passed Nov 2022)",   "State of Domicile:", "New Mexico"],
        ["AUM:",              "$148,200",                           "Tier:",              "D — Annual review"],
        ["Attorney of Record:", "Espinoza & Torres LLP, Albuquerque NM", "", ""],
    ]
    tcp = Table(cp_data, colWidths=[1.35 * inch, 2.3 * inch, 1.35 * inch, 2.2 * inch])
    tcp.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, -1), ROW_ALT),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("PADDING",    (0, 0), (-1, -1), 5),
        ("SPAN",       (1, 3), (-1, 3)),
    ]))
    story.append(tcp)

    # Core documents checklist
    story.append(Paragraph("CORE ESTATE PLANNING DOCUMENTS", styles["Section"]))
    doc_data = [
        ["Document",                           "Status",       "Date Executed", "Last Reviewed",  "Action Required"],
        ["Last Will & Testament",              "Current",      "Nov 8, 2023",   "Nov 8, 2023",    "None — update if assets change"],
        ["Revocable Living Trust",             "MISSING",      "—",             "—",               "CONSULT ATTORNEY — probate avoidance"],
        ["Durable Power of Attorney",          "Current",      "Nov 8, 2023",   "Nov 8, 2023",    "None"],
        ["Healthcare Directive / Living Will", "Current",      "Nov 8, 2023",   "Feb 10, 2026",   "None"],
        ["HIPAA Authorization",                "OUTDATED",     "Mar 12, 2018",  "Never",           "UPDATE — NM law changed 2021"],
        ["IRA Beneficiary Designations",       "REVIEW",       "Jun 2022",      "Jun 2022",        "UPDATE — spouse deceased; name children"],
        ["Life Insurance Beneficiary",         "REVIEW",       "Jun 2022",      "Jun 2022",        "UPDATE — confirm current beneficiary"],
        ["Transfer-on-Death Deed",             "MISSING",      "—",             "—",               "RECOMMENDED — NM Stat. Sec. 45-6-401"],
    ]
    col_w2 = [1.5, 0.82, 0.88, 0.88, 2.32]
    td2 = Table(doc_data, colWidths=[w * inch for w in col_w2])
    td2.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT2]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("PADDING",     (0, 0), (-1, -1), 4),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        # Status color coding
        ("TEXTCOLOR",   (1, 3), (1, 3), RED),   ("FONTNAME", (1, 3), (1, 3), "Helvetica-Bold"),
        ("TEXTCOLOR",   (1, 6), (1, 6), ORANGE), ("FONTNAME", (1, 6), (1, 6), "Helvetica-Bold"),
        ("TEXTCOLOR",   (1, 7), (1, 8), ORANGE), ("FONTNAME", (1, 7), (1, 8), "Helvetica-Bold"),
        ("TEXTCOLOR",   (1, 9), (1, 9), RED),   ("FONTNAME", (1, 9), (1, 9), "Helvetica-Bold"),
        # Action color coding
        ("TEXTCOLOR",   (4, 3), (4, 3), RED),   ("FONTNAME", (4, 3), (4, 3), "Helvetica-Bold"),
        ("TEXTCOLOR",   (4, 6), (4, 9), RED),   ("FONTNAME", (4, 6), (4, 9), "Helvetica-Bold"),
    ]))
    story.append(td2)

    # Asset distribution plan
    story.append(Paragraph("ASSET DISTRIBUTION PLAN", styles["Section"]))
    ad_data = [
        ["Asset",                     "Value (est.)", "Current Designation",  "Passes Via",       "Issue"],
        ["Traditional IRA (Schwab)",  "$98,400",      "Spouse (deceased)",    "Beneficiary Desig.", "UPDATE immediately"],
        ["Roth IRA (Schwab)",         "$24,800",      "Spouse (deceased)",    "Beneficiary Desig.", "UPDATE immediately"],
        ["Individual Brokerage",      "$18,200",      "Estate / Will",        "Probate",            "Consider TOD account"],
        ["Checking / Savings",        "$6,800",       "Estate",               "Probate",            "Add POD designation"],
        ["Personal Property",         "~$15,000",     "Per Will",             "Probate",            "Document item list"],
    ]
    tad = Table(ad_data, colWidths=[1.5 * inch, 0.9 * inch, 1.55 * inch, 1.15 * inch, 1.9 * inch])
    tad.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT2]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("PADDING",     (0, 0), (-1, -1), 4),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR",   (4, 1), (4, 2), RED),
        ("FONTNAME",    (4, 1), (4, 2), "Helvetica-Bold"),
    ]))
    story.append(tad)

    # Priority action items
    story.append(Paragraph("PRIORITY ACTION ITEMS", styles["Section"]))
    actions = [
        ("URGENT", "Update IRA beneficiary designations — both Traditional and Roth IRA still list "
         "deceased spouse. Complete Schwab Beneficiary Designation form. Recommend naming "
         "children as equal primary beneficiaries. Can be done online or at branch."),
        ("HIGH",   "Update HIPAA Authorization to comply with 2021 NM Health Information Privacy "
         "Act amendments. Espinoza & Torres LLP will mail updated forms within 30 days."),
        ("HIGH",   "Confirm and update life insurance beneficiary. Obtain all policy details "
         "from client at next meeting."),
        ("MEDIUM", "Evaluate Revocable Living Trust — gross estate ~$163K; NM probate fees "
         "approx. 3-4%. Consult Espinoza & Torres LLP for cost-benefit analysis."),
        ("MEDIUM", "Execute Transfer-on-Death Deed for any real property owned. NM TOD deed "
         "statute enacted 2015 (NM Stat. Sec. 45-6-401); avoids probate at no cost."),
        ("LOW",    "Create personal property memorandum to accompany Will — list specific "
         "bequests for jewelry, artwork, and family heirlooms."),
    ]
    act_data = [["Priority", "Action Item"]] + [[p, desc] for p, desc in actions]
    ta2 = Table(act_data, colWidths=[0.78 * inch, 6.12 * inch])
    ta2.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",    (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT2]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("PADDING",     (0, 0), (-1, -1), 5),
        ("TEXTCOLOR",   (0, 1), (0, 1), RED),
        ("TEXTCOLOR",   (0, 2), (0, 3), ORANGE),
        ("TEXTCOLOR",   (0, 4), (0, 5), BLUE),
        ("TEXTCOLOR",   (0, 6), (0, 6), GREEN),
    ]))
    story.append(ta2)

    # Follow-up
    story.append(Paragraph("NEXT STEPS & FOLLOW-UP", styles["Section"]))
    story.append(Paragraph(
        "<b>Scheduled Follow-Up:</b> April 15, 2026 — beneficiary update confirmation meeting. "
        "Client to bring Schwab account numbers and copies of all IRA statements.",
        styles["Body"]))
    story.append(Paragraph(
        "<b>Attorney Coordination:</b> Espinoza & Torres LLP notified of HIPAA update "
        "requirement and IRA beneficiary review need. Follow-up call scheduled March 20, 2026.",
        styles["Body"]))

    _footer(story,
            "This checklist is prepared by the advisor for planning purposes and does not constitute legal advice.",
            styles)
    doc.build(story)
    print(f"  Created: {path.name}  (CLT040 Carol Martinez)")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    styles = make_styles()

    sep = "-" * 56
    print(f"\n{sep}")
    print("  WealthRadar — Generating sample PDF documents")
    print(sep)

    generate_johnson_trust(styles)
    generate_smith_account_statement(styles)
    generate_davis_tax_return(styles)
    generate_wilson_insurance(styles)
    generate_martinez_estate_plan(styles)

    print(sep)
    print("  Output: backend/app/data/documents/")
    print()
    print("  Client mappings:")
    print("    johnson_trust.pdf            -> CLT001  Mark Johnson   (Tier A, age 77)")
    print("    smith_account_statement.pdf  -> CLT002  (Tier A, age 74, portfolio drift)")
    print("    davis_tax_return_summary.pdf -> CLT005  (Tier A, age 62, TLH opportunity)")
    print("    wilson_insurance_policy.pdf  -> CLT013  (Tier B, age 66)")
    print("    martinez_estate_plan.pdf     -> CLT040  Carol Martinez (Tier D, age 69)")
    print(sep + "\n")


if __name__ == "__main__":
    main()
