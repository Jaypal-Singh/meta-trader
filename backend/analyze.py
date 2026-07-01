import pandas as pd

def analyze_trades():
    try:
        df = pd.read_csv('c:/Users/Administrator/Documents/meta-trader/backend/trade_analysis.csv')
        # Filter only CLOSE actions
        df_close = df[df['action'] == 'CLOSE']
        
        print("Total Closed Trades:", len(df_close))
        print("Total Net PnL:", df_close['net_pnl'].sum())
        print("\n--- By Strategy ---")
        strat_group = df_close.groupby('strategy').agg(
            trades=('ticket', 'count'),
            win_rate=('net_pnl', lambda x: (x > 0).mean() * 100),
            total_pnl=('net_pnl', 'sum'),
            avg_pnl=('net_pnl', 'mean')
        )
        print(strat_group)
        
        print("\n--- By Timeframe ---")
        tf_group = df_close.groupby('timeframe').agg(
            trades=('ticket', 'count'),
            win_rate=('net_pnl', lambda x: (x > 0).mean() * 100),
            total_pnl=('net_pnl', 'sum')
        )
        print(tf_group)
        
        print("\n--- By Symbol ---")
        sym_group = df_close.groupby('symbol').agg(
            trades=('ticket', 'count'),
            win_rate=('net_pnl', lambda x: (x > 0).mean() * 100),
            total_pnl=('net_pnl', 'sum')
        )
        print(sym_group)
        
        print("\n--- By Reason ---")
        reason_group = df_close.groupby('reason').agg(
            trades=('ticket', 'count'),
            win_rate=('net_pnl', lambda x: (x > 0).mean() * 100),
            total_pnl=('net_pnl', 'sum')
        )
        print(reason_group)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_trades()
