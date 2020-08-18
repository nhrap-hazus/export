import os
import win32com.client as win32


def draftEmail():
    def createDraftEmail(text, subject, recipient, send=True):

        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.To = recipient
        mail.Subject = subject
        mail.HtmlBody = text
        if send:
            mail.send()
        else:
            mail.save()
    msg = """
    <html>
    <head>
        <style type="text/css">
            .results-container {
                margin: 0;
                padding: 0;
                list-style: none;
            }
            .results {
                list-style-type: disc;
            }
            .results-details {
                list-style-type: circle;
            }
        </style>
    </head>
    <html>
    <body>
    <p>Greetings,</p>
    <p>The Hazus team has completed the run of record, Hazus hurricane wind modeling for Hurricane Isaias based on Advisory 32.  Our analysis includes the states of Florida, South Carolina, North Carolina, and Virginia.  Hazus does not generate impact assessments for wind below 50 mph, and so states with lower windspeeds were excluded.  Attached are Hazus results, and a snapshot summary is below:</p>
    <strong>Hurricane Isaias Hazus Hurricane Wind Run of Record Advisory 32 Loss Summary</strong>
    <br />
    <br />
    <strong>Florida</strong>
    <ul class="results-container">
        <ul class="results">
            <li>$490.31 K in Total Economic Loss. The 5 counties with the highest modeled economic impacts are below:</li>
            <ul class="results-details">
                <li>$355.32 K – Palm Beach</li>
                <li>$92.50 K – St. Lucie</li>
                <li>$22.31 K – Broward</li>
            </ul>
        </ul>
        <ul class="results">
            <li>Number of Residential Buildings Damaged</li>
            <ul class="results-details">
                <li>Affected – 577</li>
                <li>Minor – 17</li>
                <li>Major/Destroyed – < 10</li>
            </ul>
        </ul>
        <ul class="results">
            <li>< 10 Displaced Household and < 10 Short-Term Shelter Needs</li>
        </ul>
        <ul class="results">
            <li>60 Total Tons of Debris</li>
            <ul class="results-details">
                <li>60 tons of Brick/Wood Debris</li>
                <li>0 tons of Concrete/Steel Debris</li>
                <li>0 tons of Tree Debris</li>
            </ul>
        </ul>
    </ul>
    </body>
    </html>
    """
    createDraftEmail(msg, "Hurricane Whatever for Advisory BowWow", "", send=False)