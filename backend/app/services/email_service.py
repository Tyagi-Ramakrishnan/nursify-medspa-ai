"""
Email service — sends the daily HTML report via SMTP.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings


def send_report_email(report_data: dict) -> bool:
    """Send the daily report email. Returns True on success."""
    html = _render_report_html(report_data)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Nursify MedSpa AI Daily Report — {report_data['date']}"
    msg["From"] = settings.REPORT_FROM_EMAIL
    msg["To"] = settings.REPORT_TO_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.REPORT_FROM_EMAIL, settings.REPORT_TO_EMAIL, msg.as_string())
        return True
    except Exception as e:
        print(f"[email] Failed to send report: {e}")
        return False


def _render_report_html(data: dict) -> str:
    """
    Render the daily report as a clean HTML email.
    No external dependencies — plain inline-styled HTML for maximum email client compatibility.
    """
    date_str = data.get("date", "")
    revenue = data.get("total_revenue", 0)
    expenses = data.get("total_expenses", 0)
    fees = data.get("total_fees", 0)
    net = data.get("net_income", 0)
    txn_count = data.get("transaction_count", 0)
    pending = data.get("pending_count", 0)
    categories = data.get("category_breakdown", {})
    sources = data.get("source_breakdown", {})

    net_color = "#0F6E56" if net >= 0 else "#A32D2D"

    category_rows = "".join(
        f"""<tr>
              <td style="padding:6px 0;color:#444;border-bottom:1px solid #f0f0f0">{cat}</td>
              <td style="padding:6px 0;text-align:right;border-bottom:1px solid #f0f0f0">${amt:,.2f}</td>
            </tr>"""
        for cat, amt in sorted(categories.items(), key=lambda x: -x[1])
    )

    source_rows = "".join(
        f"""<tr>
              <td style="padding:6px 0;color:#444;border-bottom:1px solid #f0f0f0">{src}</td>
              <td style="padding:6px 0;text-align:right;border-bottom:1px solid #f0f0f0">${amt:,.2f}</td>
            </tr>"""
        for src, amt in sorted(sources.items(), key=lambda x: -x[1])
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:32px 16px">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden">

            <!-- Header -->
            <tr>
              <td style="background:#085041;padding:24px 32px">
                <p style="margin:0;color:#9FE1CB;font-size:13px;text-transform:uppercase;letter-spacing:1px">Nursify MedSpa AI</p>
                <h1 style="margin:4px 0 0;color:#fff;font-size:22px;font-weight:500">Daily Report</h1>
                <p style="margin:4px 0 0;color:#9FE1CB;font-size:14px">{date_str}</p>
              </td>
            </tr>

            <!-- Key numbers -->
            <tr>
              <td style="padding:24px 32px">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="width:25%;text-align:center;padding:12px 8px;background:#f8f8f8;border-radius:6px">
                      <p style="margin:0;font-size:12px;color:#888">Revenue</p>
                      <p style="margin:4px 0 0;font-size:20px;font-weight:500;color:#0F6E56">${revenue:,.2f}</p>
                    </td>
                    <td style="width:4%"></td>
                    <td style="width:25%;text-align:center;padding:12px 8px;background:#f8f8f8;border-radius:6px">
                      <p style="margin:0;font-size:12px;color:#888">Expenses</p>
                      <p style="margin:4px 0 0;font-size:20px;font-weight:500;color:#444">${expenses:,.2f}</p>
                    </td>
                    <td style="width:4%"></td>
                    <td style="width:25%;text-align:center;padding:12px 8px;background:#f8f8f8;border-radius:6px">
                      <p style="margin:0;font-size:12px;color:#888">Fees</p>
                      <p style="margin:4px 0 0;font-size:20px;font-weight:500;color:#444">${fees:,.2f}</p>
                    </td>
                    <td style="width:4%"></td>
                    <td style="width:25%;text-align:center;padding:12px 8px;background:#f8f8f8;border-radius:6px">
                      <p style="margin:0;font-size:12px;color:#888">Net income</p>
                      <p style="margin:4px 0 0;font-size:20px;font-weight:500;color:{net_color}">${net:,.2f}</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:12px 0 0;font-size:13px;color:#888">{txn_count} transactions &nbsp;·&nbsp; {pending} pending</p>
              </td>
            </tr>

            <!-- Category breakdown -->
            {"" if not categories else f'''
            <tr>
              <td style="padding:0 32px 24px">
                <p style="margin:0 0 12px;font-size:14px;font-weight:500;color:#222">Revenue by service</p>
                <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px">
                  {category_rows}
                </table>
              </td>
            </tr>'''}

            <!-- Source breakdown -->
            {"" if not sources else f'''
            <tr>
              <td style="padding:0 32px 24px">
                <p style="margin:0 0 12px;font-size:14px;font-weight:500;color:#222">Revenue by source</p>
                <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px">
                  {source_rows}
                </table>
              </td>
            </tr>'''}

            <!-- Footer -->
            <tr>
              <td style="padding:16px 32px;background:#f8f8f8;border-top:1px solid #eee">
                <p style="margin:0;font-size:12px;color:#aaa">Generated by Nursify MedSpa AI &nbsp;·&nbsp; Data sourced from QuickBooks</p>
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
