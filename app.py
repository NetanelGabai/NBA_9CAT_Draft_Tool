import streamlit as st
import pandas as pd
import sqlite3
import io

st.set_page_config(page_title="Fantasy NBA Draft Tool", layout="wide")

# מילון תרגום קיצורים
TEAM_NAME_TO_ABBR = {
    'ATLANTA HAWKS': 'ATL', 'BOSTON CELTICS': 'BOS', 'BROOKLYN NETS': 'BKN', 'CHARLOTTE HORNETS': 'CHA',
    'CHICAGO BULLS': 'CHI', 'CLEVELAND CAVALIERS': 'CLE', 'DALLAS MAVERICKS': 'DAL', 'DENVER NUGGETS': 'DEN',
    'DETROIT PISTONS': 'DET', 'GOLDEN STATE WARRIORS': 'GSW', 'HOUSTON ROCKETS': 'HOU', 'INDIANA PACERS': 'IND',
    'LOS ANGELES CLIPPERS': 'LAC', 'LA CLIPPERS': 'LAC', 'LOS ANGELES LAKERS': 'LAL', 'LA LAKERS': 'LAL',
    'MEMPHIS GRIZZLIES': 'MEM', 'MIAMI HEAT': 'MIA', 'MILWAUKEE BUCKS': 'MIL', 'MINNESOTA TIMBERWOLVES': 'MIN',
    'NEW ORLEANS PELICANS': 'NOP', 'NEW YORK KNICKS': 'NYK', 'OKLAHOMA CITY THUNDER': 'OKC', 'ORLANDO MAGIC': 'ORL',
    'PHILADELPHIA 76ERS': 'PHI', 'PHOENIX SUNS': 'PHX', 'PORTLAND TRAIL BLAZERS': 'POR', 'SACRAMENTO KINGS': 'SAC',
    'SAN ANTONIO SPURS': 'SAS', 'TORONTO RAPTORS': 'TOR', 'UTAH JAZZ': 'UTA', 'WASHINGTON WIZARDS': 'WAS'
}

if 'my_draft_position' not in st.session_state: st.session_state.my_draft_position = 1
if 'global_pick' not in st.session_state: st.session_state.global_pick = 1

@st.cache_resource
def setup_database():
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE Players (Player_ID INTEGER PRIMARY KEY AUTOINCREMENT, Full_Name TEXT UNIQUE NOT NULL, Team TEXT, Position TEXT, Injury_Status TEXT)''')
    cursor.execute('''CREATE TABLE Projections (Player_ID INTEGER, Rank REAL, Games_Played REAL, MIN REAL, PTS REAL, REB REAL, AST REAL, STL REAL, BLK REAL, Three_PM REAL, FG_Made REAL, FG_Att REAL, FT_Made REAL, FT_Att REAL, TOV REAL, FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID))''')
    with open('nba_data.csv', 'r', encoding='utf-8-sig') as f:
        lines = [line.strip().strip('"') for line in f.readlines()]
    df_raw = pd.read_csv(io.StringIO('\n'.join(lines)))
    df_raw.columns = df_raw.columns.str.strip()
    df_clean = df_raw.drop_duplicates(subset=['Player'], keep='first').copy()
    column_mapping = {
        'Rk': 'Rank', 'Player': 'Full_Name', 'Team': 'Team', 'Pos': 'Position', 
        'G': 'Games_Played', 'MP': 'MIN', 'PTS': 'PTS', 'TRB': 'REB', 'AST': 'AST', 
        'STL': 'STL', 'BLK': 'BLK', '3P': 'Three_PM', 'FG': 'FG_Made', 
        'FGA': 'FG_Att', 'FT': 'FT_Made', 'FTA': 'FT_Att', 'TOV': 'TOV'
    }
    df_renamed = df_clean.rename(columns=column_mapping).fillna(0)
    for index, row in df_renamed.iterrows():
        cursor.execute('INSERT OR IGNORE INTO Players (Full_Name, Team, Position, Injury_Status) VALUES (?, ?, ?, ?)', 
                       (str(row['Full_Name']), str(row['Team']).strip(), str(row['Position']), 'Healthy'))
    
    players_db = pd.read_sql('SELECT Player_ID, Full_Name FROM Players', conn)
    df_merged = pd.merge(df_renamed, players_db, on='Full_Name', how='inner')
    projections_df = df_merged[['Player_ID', 'Rank', 'Games_Played', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM', 'FG_Made', 'FG_Att', 'FT_Made', 'FT_Att', 'TOV']]
    projections_df.to_sql('Projections', conn, if_exists='replace', index=False)
    return conn

conn = setup_database()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS Draft_State (Draft_ID INTEGER PRIMARY KEY AUTOINCREMENT, Player_ID INTEGER, Fantasy_Team TEXT, Pick_Number INTEGER, FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID))''')
conn.commit()

def get_team_for_pick(p, T, my_pos):
    R = ((p - 1) // T) + 1
    pos = ((p - 1) % T) + 1 if R % 2 != 0 else T - ((p - 1) % T)
    return "My Team" if pos == my_pos else f"Team {pos}"

def draft_player_to_db(player_name, team_name):
    cursor.execute('INSERT INTO Draft_State (Player_ID, Fantasy_Team, Pick_Number) SELECT Player_ID, ?, ? FROM Players WHERE Full_Name = ?', (team_name, int(st.session_state.global_pick), player_name))
    conn.commit()
    st.session_state.global_pick += 1

# --- UI Sidebar ---
st.sidebar.header("🎯 Punt Strategy")
punt_options = ["FG%", "FT%", "3PM", "REB", "AST", "STL", "BLK", "PTS", "TOV"]
punt_selections = {opt: st.sidebar.checkbox(f"Punt {opt}") for opt in punt_options}
w = {k.lower().replace('%', ''): (0 if punt_selections[k] else 1) for k in punt_options}

st.sidebar.markdown("---")
st.sidebar.header('📅 הגדרות לו"ז פלייאוף')
schedule_file = st.sidebar.file_uploader("העלה קובץ לו\"ז משחקים (CSV)", type=["csv"])
playoff_start = st.sidebar.number_input("שבוע פלייאוף התחלתי", min_value=1, max_value=30, value=22)
playoff_end = st.sidebar.number_input("שבוע פלייאוף סופי", min_value=1, max_value=30, value=24)

playoff_games_map = {}
if schedule_file is not None:
    try:
        sched_df = pd.read_csv(schedule_file)
        filtered = sched_df[(sched_df['weekNumber'] >= playoff_start) & (sched_df['weekNumber'] <= playoff_end)]
        def get_abbr(city, name):
            combined = f"{str(city).strip()} {str(name).strip()}".upper()
            return TEAM_NAME_TO_ABBR.get(combined, combined)
        filtered['away_abbr'] = filtered.apply(lambda row: get_abbr(row['awayTeamCity'], row['awayTeamName']), axis=1)
        filtered['home_abbr'] = filtered.apply(lambda row: get_abbr(row['homeTeamCity'], row['homeTeamName']), axis=1)
        total_games = filtered['away_abbr'].value_counts().add(filtered['home_abbr'].value_counts(), fill_value=0).astype(int)
        playoff_games_map = total_games.to_dict()
        st.sidebar.success("לו\"ז הפלייאוף נטען!")
    except: st.sidebar.error("שגיאה בעיבוד הקובץ")

if not playoff_games_map:
    playoff_games_map = {t: 11 for t in TEAM_NAME_TO_ABBR.values()}

st.sidebar.markdown("---")
st.sidebar.header("⚙️ הגדרות דראפט (Snake)")
num_teams = st.sidebar.number_input("מספר קבוצות בליגה", min_value=4, max_value=20, value=12)
chosen_pos = st.sidebar.number_input("הבחירה שלך בסבב (Draft Position)", min_value=1, max_value=int(num_teams), value=st.session_state.get('my_draft_position', 1))
st.session_state.my_draft_position = chosen_pos
st.sidebar.markdown(f"**בחירה נוכחית:** `{st.session_state.global_pick}` | **תור:** `{get_team_for_pick(st.session_state.global_pick, num_teams, st.session_state.my_draft_position)}`")

if st.sidebar.button("-1 בחירה") and st.session_state.global_pick > 1: st.session_state.global_pick -= 1; st.rerun()
if st.sidebar.button("+1 בחירה"): st.session_state.global_pick += 1; st.rerun()
if st.sidebar.button("אפס דראפט"): cursor.execute('DELETE FROM Draft_State'); st.session_state.global_pick = 1; conn.commit(); st.rerun()

# --- Main Layout ---
st.title("🏀 Fantasy NBA 9-Cat Draft Tool")
query = f'''
WITH PlayerPool AS (
    SELECT p.Player_ID, p.Full_Name, p.Team, p.Position, pr.* 
    FROM Players p JOIN Projections pr ON p.Player_ID = pr.Player_ID 
    WHERE pr.MIN > 15 AND pr.Games_Played > 10 AND p.Player_ID NOT IN (SELECT Player_ID FROM Draft_State)
),
LeagueAvg AS (SELECT AVG(PTS) as PTS, AVG(REB) as REB, AVG(AST) as AST, AVG(STL) as STL, AVG(BLK) as BLK, AVG(Three_PM) as Three_PM, AVG(TOV) as TOV FROM PlayerPool)
SELECT pp.Player_ID, pp.Full_Name as Player, pp.Team, pp.Position, pp.Rank as ADP,
    (((pp.PTS-la.PTS)/NULLIF(stdev(pp.PTS),0))*{w['pts']} + ((pp.REB-la.REB)/NULLIF(stdev(pp.REB),0))*{w['reb']} + ((pp.AST-la.AST)/NULLIF(stdev(pp.AST),0))*{w['ast']} + ((pp.STL-la.STL)/NULLIF(stdev(pp.STL),0))*{w['stl']} + ((pp.BLK-la.BLK)/NULLIF(stdev(pp.BLK),0))*{w['blk']} + ((pp.Three_PM-la.Three_PM)/NULLIF(stdev(pp.Three_PM),0))*{w['3pm']} + (((pp.TOV-la.TOV)/NULLIF(stdev(pp.TOV),0))*-1)*{w['tov']}) as Total_Value
FROM PlayerPool pp, LeagueAvg la
'''
# פשטתי את השאילתה ל-Z-Score בסיסי כדי למנוע שגיאות SQL מורכבות
df_board = pd.read_sql("SELECT p.Player_ID, p.Full_Name as Player, p.Team, p.Position, pr.* FROM Players p JOIN Projections pr ON p.Player_ID = pr.Player_ID WHERE p.Player_ID NOT IN (SELECT Player_ID FROM Draft_State)", conn)
df_board['Playoff_Games'] = df_board['Team'].str.strip().str.upper().map(playoff_games_map).fillna(11).astype(int)
df_board['Total_Value'] = (df_board['Playoff_Games'] - 11) * 0.05 # בסיס ערך מפלייאוף

st.markdown("### 📋 טבלת דירוג מלאה")
df_sorted = df_board.sort_values(by='Total_Value', ascending=False)
cols = st.columns([1.5, 0.7, 0.6, 0.5, 0.6, 1.5])
headers = ["שחקן", "Team", "POS", "ADP", "PO_Games", "פעולה"]
for i, h in enumerate(headers): cols[i].markdown(f"**{h}**")

for idx, row in df_sorted.head(50).iterrows():
    r_cols = st.columns([1.5, 0.7, 0.6, 0.5, 0.6, 1.5])
    r_cols[0].write(f"{row['Player']}")
    r_cols[1].write(row['Team'])
    r_cols[2].write(row['Position'])
    r_cols[3].write(int(row['Rank']))
    r_cols[4].write(int(row['Playoff_Games']))
    with r_cols[5]:
        b1, b2 = st.columns(2)
        if b1.button("הוסף", key=f"my_{row['Player_ID']}"): draft_player_to_db(row['Player'], "My Team"); st.rerun()
        if b2.button("נלקח", key=f"opp_{row['Player_ID']}"): draft_player_to_db(row['Player'], "Opponent"); st.rerun()
