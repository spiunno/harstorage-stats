from flask import Flask, render_template, abort, redirect
from flask.helpers import url_for
from gviz_data_table import Table, encode
from couchbase import Couchbase
from datetime import date, datetime, timedelta
import json

app = Flask(__name__)
app.cb = Couchbase.connect(
    host='http://10.1.20.55', 
    bucket='harstorage')
app.view = 'results'

def menu():
    reports = (
        ('trendmonthly', 'Monthly trend'),
        ('trendweekly', 'Weekly trend'),
        ('trenddaily', 'Daily trend'),
        ('monththis', 'This month'),
    )
    return [{'url': url_for(endpoint), 'title': title} 
        for endpoint, title in reports]

@app.route('/')
def index():
    return render_template('index.html', items=menu())

@app.route('/trend/daily')
def trenddaily():
    url = url_for('bycountryday')
    return render_template('trend.html', url=url, items=menu())

@app.route('/trend/weekly')
def trendweekly():
    url = url_for('bycountryweek')
    return render_template('trend.html', url=url, items=menu())

@app.route('/trend/monthly')
def trendmonthly():
    url = url_for('bycountrymonth')
    return render_template('trend.html', url=url, items=menu())

@app.route('/month')
def monththis():
    d = datetime.now().date() 
    return redirect(url_for('monthidx', qyear=d.year, qmonth=d.month))

@app.route('/label/<qlabel>/<int:qyear>/<int:qmonth>')
def label(qlabel, qyear, qmonth):
    url = url_for('onelabel', qlabel=qlabel, qyear=qyear, qmonth=qmonth)
    title = 'Timeline for %s' % qlabel
    #url = '/api/label/%s/%s/%s/%s' % (qlabel, qyear, qmonth, qtype)
    return render_template('onelabel.html', d=locals(), items=menu())

@app.route('/month/<int:qyear>/<int:qmonth>')
def monthidx(qyear, qmonth):
    thismonth = date(qyear, qmonth, 1)
    title = "Monthly average for %s" % thismonth.strftime('%B %Y')
    lastmonth = url_for('monthidx', qyear=(qmonth>1 and qyear or qyear-1), 
        qmonth=(qmonth>1 and qmonth-1 or 12))
    nextmonth = url_for('monthidx', qyear=(qmonth<12 and qyear or qyear+1), 
        qmonth=(qmonth<12 and qmonth+1 or 1))
    url = url_for('onemonth', qyear=qyear, qmonth=qmonth)
    items = menu()
    items.append({'url':lastmonth, 'title':"Prev month"});
    items.append({'url':nextmonth, 'title':"Next month"});
    return render_template('onemonth.html', d=locals(), items=items)

@app.route('/api/label/<qlabel>/<int:qyear>/<int:qmonth>')
def onelabel(qlabel,qyear,qmonth):
    table = Table()
    table.add_column('DateTime', datetime, "DateTime")
    table.add_column('size', int, 'Total Size (KB)')
    table.add_column('reqs', int, 'Request Count')
    table.add_column('time', int, 'Full Load time (ms)')
    for item in app.cb.query(app.view, 'bylabel', reduce=False,
            startkey=qlabel, endkey=qlabel):
        tstamp, size, reqs, time = item.value[:4]
        dt = datetime.strptime(tstamp, "%Y-%m-%d %H:%M:%S")
        if dt.year == qyear and dt.month == qmonth:
            table.append([dt, size, reqs, time])
    return encode(table)

@app.route('/api/month/<int:qyear>/<int:qmonth>')
def onemonth(qyear,qmonth):
    table = Table()
    table.add_column('label', unicode, "Label")
    table.add_column('size', int, 'Total Size (KB)')
    table.add_column('reqs', int, 'Request Count')
    table.add_column('time', int, 'Full Load time (ms)')
    for item in app.cb.query(app.view, 'bylabeldate', group=True, group_level=4):
        catclass, country, year, month = item.key
        if year == qyear and month == qmonth and catclass == 'CAT+':
            n, size, reqs, time = item.value[:4]
            table.append([country, size/n, reqs/n, time/n])
    return encode(table)

@app.route('/api/target')
def target():
    april = [0, 0]
    aprilym = date(2013, 4, 1)
    this_month = [0, 0]
    thisym = datetime.now().date().replace(day=1)
    for item in app.cb.query(app.view, 'bylabeldate', group=True, group_level=4):
        catclass, country, year, month = item.key
        ym = date(year, month, 1)
        if catclass == 'CAT+' and ym == thisym:
            nitems, totsize, totfiles, tottime = item.value[:4]
            this_month[0] += tottime
            this_month[1] += nitems
        elif catclass == 'CAT+' and ym == aprilym:
            nitems, totsize, totfiles, tottime = item.value[:4]
            april[0] += tottime
            april[1] += nitems
    aprilavg = 1.0*april[0]/april[1]
    thisavg = 1.0*this_month[0]/this_month[1]
    improvement = 1.0-thisavg/aprilavg
    d = {
        'startavg': int(aprilavg),
        'endavg': int(thisavg),
        'improvement': '%.2f%%' % (100*improvement),
    }
    return json.dumps(d)

@app.route('/api/bycountry/dailytrend')
def bycountryday():
    table = Table()
    table.add_column('Day', date, "Day")
    countries = set()
    t = {}
    #for item in cb.query('results', 'bylabeldate', group=True, group_level=4):
    for item in app.cb.query(app.view, 'bylabeldate', group=True, group_level=5):
        catclass, country, year, month, day = item.key
        if catclass == 'CAT+':
            countries.add(country)
            nitems, totsize, totfiles, tottime = item.value[:4]
            ymd = date(year, month, day)
            if ymd not in t: t[ymd] = {}
            t[ymd][country] = tottime/nitems
    countries = list(countries)
    countries.sort()
    for country in countries:
        table.add_column(country, int, country)
    days = t.keys()
    days.sort()   
    for day in days[2:-1]:
        line = [{'value':day, 'label':day.strftime('%Y-%m-%d')}]
        for country in countries:
            line.append(t[day].get(country, None))
        table.append(line)
    return encode(table)

@app.route('/api/bycountry/monthlytrend')
def bycountrymonth():
    table = Table()
    table.add_column('Month', date, "Month")
    countries = set()
    t = {}
    #for item in cb.query('results', 'bylabeldate', group=True, group_level=4):
    for item in app.cb.query(app.view, 'bylabeldate', group=True, group_level=4):
        catclass, country, year, month = item.key
        if catclass == 'CAT+':
            countries.add(country)
            nitems, totsize, totfiles, tottime = item.value[:4]
            ym = date(year, month, 1)
            if ym not in t: t[ym] = {}
            t[ym][country] = tottime/nitems
    countries = list(countries)
    countries.sort()
    for country in countries:
        table.add_column(country, int, country)
    months = t.keys()
    months.sort()   
    for month in months[2:-1]:
        line = [{'value':month, 'label':month.strftime('%Y-%m')}]
        for country in countries:
            line.append(t[month].get(country, None))
        table.append(line)
    return encode(table)

@app.route('/api/bycountry/weeklytrend')
def bycountryweek():
    table = Table()
    table.add_column('Week', date, "Week")
    countries = set()
    t = {}
    #for item in cb.query('results', 'bylabeldate', group=True, group_level=4):
    for item in app.cb.query(app.view, 'bylabelweek', group=True):
        catclass, country, year, month, day = item.key
        if catclass == 'CAT+':
            countries.add(country)
            nitems, totsize, totfiles, tottime = item.value
            ym = date(year, month, day)
            if ym not in t: t[ym] = {}
            t[ym][country] = tottime/nitems
    countries = list(countries)
    countries.sort()
    for country in countries:
        table.add_column(country, int, country)
    weeks = t.keys()
    weeks.sort()   
    for week in weeks:
        line = [week]
        for country in countries:
            line.append(t[week].get(country, None))
        table.append(line)
    return encode(table)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
