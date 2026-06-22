import json, urllib.request, datetime

data = json.loads(urllib.request.urlopen('http://localhost:8000/api/trading/chart_data?symbol=XAUUSD&timeframe=M5').read())

signals = [d for d in data if d.get('signal')]
buys  = [d for d in signals if d['signal'] == 'BUY']
sells = [d for d in signals if d['signal'] == 'SELL']
print(f'Total candles: {len(data)}')
print(f'Total signals: {len(signals)} (BUY: {len(buys)}, SELL: {len(sells)})')

# Show the LAST 15 candles — we should see signals on the most recent ones now
print('\n=== LAST 15 CANDLES (should have instant signals) ===')
for d in data[-15:]:
    ts = datetime.datetime.fromtimestamp(d['time'], datetime.UTC).strftime('%H:%M')
    sig = d.get('signal', '-')
    marker = '  <<<' if sig != '-' and sig is not None else ''
    sig_str = sig if sig else '-'
    print(f"  {ts}  close={d['close']:.2f}  signal={sig_str}{marker}")

# Most recent signal
last_sig = [d for d in data if d.get('signal')]
if last_sig:
    ls = last_sig[-1]
    ts = datetime.datetime.fromtimestamp(ls['time'], datetime.UTC).strftime('%H:%M')
    bars_ago = len(data) - 1 - data.index(ls)
    print(f'\nMost recent signal: {ls["signal"]} at {ts} ({bars_ago} bars ago)')
