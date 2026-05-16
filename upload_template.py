import boto3
from botocore.exceptions import ClientError


def upload_ses_template():
    ses = boto3.client('ses', region_name='eu-north-1')
    template_name = "LetterGator_Delivery_Template"

    # Minimalist design: Clean typography, plenty of whitespace
    html_content = """
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; background-color: #ffffff;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0">
            <tr>
                <td align="center" style="padding: 80px 20px;">
                    <table width="600" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px;">
                        <tr>
                            <td style="color: #1a1a1a; font-size: 18px;
                            line-height: 1.6; letter-spacing: -0.01em;">
                                {{message}}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding-top: 60px; border-top: 1px solid #f0f0f0; margin-top: 60px;">
                                <p style="color: #999999; font-size: 12px; text-transform: uppercase;
                                letter-spacing: 0.1em;">
                                    Sent via Private Delivery
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    template_config = {
        'TemplateName': template_name,
        'SubjectPart': "{{subject}}",  # Pulls subject from DynamoDB
        'HtmlPart': html_content,
        'TextPart': "{{message}}"
    }

    try:
        ses.create_template(Template=template_config)
        print(f"Successfully created template: {template_name}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'AlreadyExists':
            ses.update_template(Template=template_config)
            print(f"Successfully updated template: {template_name}")
        else:
            print(f"Error: {e}")


if __name__ == "__main__":
    upload_ses_template()
