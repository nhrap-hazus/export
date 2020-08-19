import os
import win32com.client as win32


def draftEmail(studyRegion):
    def abbreviateValue(number):
        try:
            digits = 0
            number = float(number)
            formattedString = str("{:,}".format(round(number, digits)))
            if ('.' in formattedString) and (digits == 0):
                formattedString = formattedString.split('.')[0]
            if (number > 1000) and (number < 1000000):
                split = formattedString.split(',')
                formattedString = split[0] + '.' + split[1][0:-1] + ' K'
            if (number > 1000000) and (number < 1000000000):
                split = formattedString.split(',')
                formattedString = split[0] + '.' + split[1][0:-1] + ' M'
            if (number > 1000000000) and (number < 1000000000000):
                split = formattedString.split(',')
                formattedString = split[0] + '.' + split[1][0:-1] + ' B'
            if (number > 1000000000000) and (number < 1000000000000000):
                split = formattedString.split(',')
                formattedString = split[0] + '.' + split[1][0:-1] + ' T'
            return formattedString
        except:
            return str(number)

    def addCommas(number, abbreviate=False, truncate=False):
        if truncate:
            number = int(round(number))
        if abbreviate:
            number = abbreviateValue(number)
        else:
            number = "{:,}".format(number)
        return number

    def toDollars(number, abbreviate=False, truncate=False):
        if truncate:
            number = int(round(number))
        if abbreviate:
            dollars = abbreviateValue(number)
            dollars = '$' + dollars
        else:
            dollars = '$'+"{:,}".format(number)
            dollarsSplit = dollars.split('.')
            if len(dollarsSplit) > 1:
                dollars = '.'.join([dollarsSplit[0], dollarsSplit[1][0:1]])
        return dollars

    def getResidentalDamageCounts():
        sql="""select p.tract, affected * RESI as affected, minor * RESI as minor, majoranddestroyed * RESI as majoranddestroyed from 
            (select TRACT as tract, avg(MINOR) as affected, avg(MODERATE) as minor, avg(SEVERE + COMPLETE) as majoranddestroyed FROM [{s}].[dbo].[huOccResultsT]
            where Occupancy = 'RES'
            group by tract) p
            inner join
            (SELECT TRACT as tract, RESI
            FROM [{s}].[dbo].[hzBldgCountOccupT]) c
            on p.tract = c.tract""".format(s=studyRegion.name)
        queryset = studyRegion.query(sql)
        qs_counties = queryset.addCounties()
        return qs_counties

    def createDraftEmail(HTML='', subject='Hazus Wind Loss Modeling – Hurricane [HURRICANE_NAME] for Advisory [ADVISORY_NUMBER]', recipient='', send=False):

        if len(HTML) == 0:
            results = studyRegion.getResults()
            residential = getResidentalDamageCounts()
            html_df = results.merge(residential, on='tract')

            resultsHTML = ''
            listLimit = 5
            for state in html_df['state'].unique():
                slice = html_df[html_df['state'] == state]
                slice_grouped = slice.groupby(by=['county']).sum()

                # economic loss
                total_econloss = toDollars(slice['EconLoss'].sum(), abbreviate=True)
                econloss_df = slice_grouped.sort_values('EconLoss', ascending=False)[0:listLimit]
                econloss = ''
                for row in range(len(econloss_df)):
                    county = econloss_df.index[row]
                    loss = toDollars(econloss_df.iloc[row]['EconLoss'], abbreviate=True)
                    html = """<li>{l} – {c}</li>""".format(l=loss, c=county)
                    econloss += html

                # residential building damage counts
                res_affected = abbreviateValue(slice_grouped['affected'].sum())
                res_minor = abbreviateValue(slice_grouped['minor'].sum())
                res_majoranddestroyed = abbreviateValue(slice_grouped['majoranddestroyed'].sum())

                # displaced households and shelter needs
                displacedHouseholds = abbreviateValue(slice_grouped['DisplacedHouseholds'].sum())
                shelterNeeds = abbreviateValue(slice_grouped['ShelterNeeds'].sum())

                # debris
                total_debris = abbreviateValue(slice_grouped['DebrisTotal'].sum())
                debris_bw = abbreviateValue(slice_grouped['DebrisBW'].sum())
                debris_cs = abbreviateValue(slice_grouped['DebrisCS'].sum())
                debris_tree = abbreviateValue(slice_grouped['DebrisTree'].sum())
                debris_eligibleTree = abbreviateValue(slice_grouped['DebrisEligibleTree'].sum())

                update_html = """
                    <br />
                    <br />
                    <strong>"""+state+"""</strong>
                    <ul class="results-container">
                        <ul class="results">
                            <li>"""+total_econloss+""" in Total Economic Loss. The """+str(listLimit)+""" counties with the highest modeled economic impacts are below:</li>
                            <ul class="results-details">
                                """+econloss+"""
                            </ul>
                        </ul>
                        <ul class="results">
                            <li>Number of Residential Buildings Damaged</li>
                            <ul class="results-details">
                                <li>Affected – {resa}</li>
                                <li>Minor – {resm}</li>
                                <li>Major/Destroyed – {resd}</li>
                            </ul>
                        </ul>
                        <ul class="results">
                            <li>{dh} Displaced Household and {sn} Short-Term Shelter Needs</li>
                        </ul>
                        <ul class="results">
                            <li>{td} Total Tons of Debris</li>
                            <ul class="results-details">
                                <li>{dbw} tons of Brick/Wood Debris</li>
                                <li>{dcs} tons of Concrete/Steel Debris</li>
                                <li>{dt} tons of Tree Debris</li>
                                <ul>
                                    <li>{det} tons of Eligible Tree Debris</li>
                                </ul>
                            </ul>
                        </ul>
                    </ul>
                        """.format(resa=res_affected, resm=res_minor, resd=res_majoranddestroyed, dh=displacedHouseholds, sn=shelterNeeds, td=total_debris, dbw=debris_bw, dcs=debris_cs, dt=debris_tree, det=debris_eligibleTree)
                resultsHTML += update_html

            HTML = """
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
            <p>We have completed wind loss modeling for Hurricane [HURRICANE_NAME] based on Advisory [ADVISORY_NUMBER]. Hazus does not generate impact assessments for wind below 50 mph; therefore, locations with lower windspeeds were excluded from the model.  Attached are Hazus results and a snapshot summary is below:</p>
            <strong>Hurricane [HURRICANE_NAME] Hazus Hurricane Wind Loss Modeling for Advisory [ADVISORY_NUMBER] Loss Summary</strong>
            """+resultsHTML+"""
            </body>
            </html>
            """

        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.To = recipient
        mail.Subject = subject
        mail.HtmlBody = HTML
        if send:
            mail.send()
        else:
            mail.save()
    createDraftEmail()