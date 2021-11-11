import win32com.client as win32


def draftEmail(studyRegion):
    def abbreviateValue(number):
        try:
            num = float('{:.3g}'.format(number))
            magnitude = 0
            while abs(num) >= 1000:
                magnitude += 1
                num /= 1000.0
            formatted_number = '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])
            return formatted_number
        except:
            return str(number)

    def addCommas(number, abbreviate=False, truncate=False):
        if int(number) >= 10:
            if truncate:
                number = int(round(number))
            if abbreviate:
                number = abbreviateValue(number)
            else:
                number = "{:,}".format(number)
        else:
            number = ' < 10'
        return number

    def toDollars(number, abbreviate=False, truncate=False):
        if int(number) >= 1000:
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
        else:
            dollars = ' < $1k'
        return dollars

    # TODO: Figure way to get advisory number
    # def getAdvisoryNumber():
    #     pass
    #     sql="""SELECT huScenarioName as scenario FROM syHazus.dbo.huScenario"""
    #     queryset = studyRegion.query(sql)
    #     advisory_number = queryset
    #     return advisory_number

    def getResidentalDamageCounts():
        sql="""select p.tract, affected * RESI as affected, minor * RESI as minor, major * RESI as major, destroyed * RESI as destroyed from 
            (select TRACT as tract, avg(MINOR) as affected, avg(MODERATE) as minor, avg(SEVERE) as major, avg(COMPLETE) as destroyed FROM [{s}].[dbo].[huOccResultsT]
            where Occupancy = 'RES'
            group by tract) p
            inner join
            (SELECT TRACT as tract, RESI
            FROM [{s}].[dbo].[hzBldgCountOccupT]) c
            on p.tract = c.tract""".format(s=studyRegion.name)
        queryset = studyRegion.query(sql)
        qs_counties = queryset.addCounties()
        return qs_counties

# TODO: put placeholder back for Hurricane name
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
                econloss_count = len(econloss_df)
                econloss = ''
                for row in range(len(econloss_df)):
                    county = econloss_df.index[row]
                    loss = toDollars(econloss_df.iloc[row]['EconLoss'], abbreviate=True)
                    html = """<li>{l} – {c}</li>""".format(l=loss, c=county)
                    econloss += html

                # residential building damage counts
                res_affected = addCommas(slice_grouped['affected'].sum(), truncate=True)
                res_minor = addCommas(slice_grouped['minor'].sum(), truncate=True)
                res_major = addCommas(slice_grouped['major'].sum(), truncate=True)
                res_destroyed = addCommas(slice_grouped['destroyed'].sum(), truncate=True)

                # displaced households and shelter needs
                displacedHouseholds = addCommas(slice_grouped['DisplacedHouseholds'].sum(), truncate=True)
                shelterNeeds = addCommas(slice_grouped['ShelterNeeds'].sum(), truncate=True)

                # debris
                total_debris = abbreviateValue(slice_grouped['DebrisTotal'].sum())
                debris_bw = abbreviateValue(slice_grouped['DebrisBW'].sum())
                debris_cs = abbreviateValue(slice_grouped['DebrisCS'].sum())
                debris_tree = abbreviateValue(slice_grouped['DebrisTree'].sum())
                debris_eligibleTree = abbreviateValue(slice_grouped['DebrisEligibleTree'].sum())

                update_html = """
                    <br />
                    <br />
                    <strong><u>"""+state+"""</u></strong>
                    <ul class="results-container">
                        <ul class="results">
                            <li>"""+total_econloss+""" in Total Economic Loss. The """+str(econloss_count)+""" counties with the highest modeled economic impacts are below:</li>
                            <ul class="results-details">
                                """+econloss+"""
                            </ul>
                        </ul>
                        <ul class="results">
                            <li>Number of Residential Buildings Damaged</li>
                            <ul class="results-details">
                                <li>Affected – {resa}</li>
                                <li>Minor – {resmin}</li>
                                <li>Major – {resmaj}</li>
                                <li>Destroyed – {resdes}</li>
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
                                <li>{dt} tons of Tree Debris ({det} tons of tree debris on or near public right-of-way)</li>
                            </ul>
                        </ul>
                    </ul>
                        """.format(resa=res_affected, resmin=res_minor, resmaj=res_major, resdes=res_destroyed, dh=displacedHouseholds, sn=shelterNeeds, td=total_debris, dbw=debris_bw, dcs=debris_cs, dt=debris_tree, det=debris_eligibleTree)
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