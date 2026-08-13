import streamlit as st
import pandas as pd
import sqlite3
import io

# הגדרות עמוד פרימיום
st.set_page_config(page_title="Fantasy NBA Draft Tool", page_icon="🏀", layout="wide", initial_sidebar_state="expanded")

# --- CSS פרימיום מותאם אישית ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .small-font { font-size: 13px !important; white-space: nowrap !important; padding-top: 6px; color: #e2e8f0; }
    .player-name { font-weight: 600; color: #ffffff; font-size: 14px; }
    .player-meta { color: #718096; font-size: 11px; margin-left: 5px; }
    .total-value { font-weight: 800; color: #ecc94b; font-size: 14px; }
    .tier-badge { background-color: #2d3748; padding: 2px 6px; border-radius: 4px; font-weight: bold; color: #cbd5e0; font-size: 11px; }
    .center-text { text-align: center; } 
    .left-text { text-align: left; }
    div[data-testid="stScrollableContainer"] > div > div:first-child { 
        position: sticky !important; top: 0 !important; z-index: 100 !important; 
        background: rgba(14, 17, 23, 0.95) !important; backdrop-filter: blur(5px);
        border-bottom: 1px solid rgba(255,255,255,0.1) !important; 
        padding-top: 5px !important; padding-bottom: 5px !important; 
    }
    section[data-testid="stMain"] button[kind="secondary"] { 
        background-color: transparent !important; border: none !important; box-shadow: none !important; 
        font-size: 12px !important; font-weight: 700 !important; color: #a0aec0 !important; 
        padding: 0 !important; margin: 0 !important; justify-content: center !important; transition: color 0.2s ease;
    }
    section[data-testid="stMain"] button[kind="secondary"]:hover { color: #ffffff !important; background-color: transparent !important; }
    section[data-testid="stMain"] button[kind="primary"] { 
        background-color: #2d3748 !important; border: 1px solid #4a5568 !important; color: #e2e8f0 !important; 
        padding: 0px 10px !important; font-size: 12px !important; font-weight: 600 !important;
        min-height: 26px !important; height: 26px !important; border-radius: 6px !important; 
        line-height: 1 !important; transition: all 0.2s ease;
    }
    section[data-testid="stMain"] button[kind="primary"]:hover { border-color: #cbd5e0 !important; background-color: #4a5568 !important; color: #ffffff !important; }
    [data-testid="column"] { padding-left: 0.15rem !important; padding-right: 0.15rem !important; }
    .dash-card { background-color: #1a202c; border: 1px solid #2d3748; border-radius: 8px; padding: 15px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }
    </style>
""", unsafe_allow_html=True)

def color_z_score(val):
    try:
        v = float(val)
        if v >= 1.5: return f"<span style='color: #48bb78; font-weight: bold;'>{val}</span>"
        elif v >= 0.5: return f"<span style='color: #9ae6b4;'>{val}</span>"
        elif v <= -1.5: return f"<span style='color: #f56565; font-weight: bold;'>{val}</span>"
        elif v <= -0.5: return f"<span style='color: #fc8181;'>{val}</span>"
        else: return f"<span style='color: #a0aec0;'>{val}</span>"
    except: return val

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
if 'sort_col_main' not in st.session_state: st.session_state.sort_col_main = 'Total_Value'
if 'sort_asc_main' not in st.session_state: st.session_state.sort_asc_main = False
if 'watchlist' not in st.session_state: st.session_state.watchlist = []

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
    df_renamed['Rank'] = pd.to_numeric(df_renamed['Rank'], errors='coerce').fillna(999)
    for index, row in df_renamed.iterrows():
        cursor.execute('INSERT OR IGNORE INTO Players (Full_Name, Team, Position, Injury_Status) VALUES (?, ?, ?, ?)', (str(row['Full_Name']), str(row['Team']).strip(), str(row['Position']), 'Healthy'))
    players_db = pd.read_sql('SELECT Player_ID, Full_Name FROM Players', conn)
    df_merged = pd.merge(df_renamed, players_db, on='Full_Name', how='inner')
    cols_to_keep = ['Player_ID', 'Rank', 'Games_Played', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM', 'FG_Made', 'FG_Att', 'FT_Made', 'FT_Att', 'TOV']
    df_merged[cols_to_keep].to_sql('Projections', conn, if_exists='replace', index=False)
    return conn

conn = setup_database()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS Draft_State (Draft_ID INTEGER PRIMARY KEY AUTOINCREMENT, Player_ID INTEGER, Fantasy_Team TEXT, Pick_Number INTEGER, FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID))''')
conn.commit()

def get_team_for_pick(p, T, my_pos):
    R = ((p - 1) // T) + 1
    pos = ((p - 1) % T) + 1 if R % 2 != 0 else T - ((p - 1) % T)
    return "My Team" if pos == my_pos else f"Team {pos}"

def draft_player_to_db(player_name, team_name, player_id):
    cursor.execute('INSERT INTO Draft_State (Player_ID, Fantasy_Team, Pick_Number) SELECT Player_ID, ?, ? FROM Players WHERE Full_Name = ?', (team_name, int(st.session_state.global_pick), player_name))
    conn.commit()
    if player_id in st.session_state.watchlist:
        st.session_state.watchlist.remove(player_id)
    st.session_state.global_pick += 1

# --- UI Sidebar ---
st.sidebar.markdown("<h2 style='text-align: center; color: #cbd5e0;'>⚙️ דראפט ופאנטים</h2>", unsafe_allow_html=True)
num_teams = st.sidebar.number_input("קבוצות בליגה", min_value=4, max_value=20, value=12)
st.session_state.my_draft_position = st.sidebar.number_input("מיקום הבחירה שלך", min_value=1, max_value=int(num_teams), value=st.session_state.get('my_draft_position', 1))

current_picking_team = get_team_for_pick(st.session_state.global_pick, num_teams, st.session_state.my_draft_position)
st.sidebar.markdown(f"""
<div style='background-color: #2d3748; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 15px;'>
    <span style='font-size: 12px; color: #a0aec0;'>בחירה נוכחית: {st.session_state.global_pick}</span><br>
    <strong style='font-size: 16px; color: #ffffff;'>תור: {current_picking_team}</strong>
</div>
""", unsafe_allow_html=True)

col_b1, col_b2, col_b3 = st.sidebar.columns(3)
if col_b1.button("⏪ -1"): 
    if st.session_state.global_pick > 1: st.session_state.global_pick -= 1; st.rerun()
if col_b2.button("⏭️ +1"): st.session_state.global_pick += 1; st.rerun()
if col_b3.button("🔄 איפוס"): cursor.execute('DELETE FROM Draft_State'); st.session_state.global_pick = 1; st.session_state.watchlist = []; conn.commit(); st.rerun()

if st.sidebar.button("↩️ ביטול בחירה אחרונה (Undo)", use_container_width=True):
    cursor.execute('SELECT MAX(Draft_ID) FROM Draft_State')
    last_id = cursor.fetchone()[0]
    if last_id is not None:
        cursor.execute('DELETE FROM Draft_State WHERE Draft_ID = ?', (last_id,))
        conn.commit()
        if st.session_state.global_pick > 1: st.session_state.global_pick -= 1
        st.rerun()

st.sidebar.divider()

# --- AUTO-PIVOT ENGINE ---
auto_pivot = st.sidebar.toggle("🤖 מנוע Auto-Pivot", value=False, help="יזהה אוטומטית את חולשות הקבוצה שלך לאחר 3 בחירות ויכפה אסטרטגיית פאנט אופטימלית")
w = {}
punt_options = ["FG%", "FT%", "3PM", "REB", "AST", "STL", "BLK", "PTS", "TOV"]

# חישוב Auto-Pivot ברקע (אם דלוק)
auto_pivot_active = False
auto_pivot_msg = ""
if auto_pivot:
    cursor.execute("SELECT COUNT(*) FROM Draft_State WHERE Fantasy_Team='My Team'")
    if cursor.fetchone()[0] >= 3:
        auto_pivot_active = True
        base_z_query = '''
            WITH LeagueAvg AS (SELECT AVG(PTS) as avg_pts, AVG(REB) as avg_reb, AVG(AST) as avg_ast, AVG(STL) as avg_stl, AVG(BLK) as avg_blk, AVG(Three_PM) as avg_3pm, AVG(TOV) as avg_tov, SUM(FG_Made)/SUM(FG_Att) as lg_fg_pct, SUM(FT_Made)/SUM(FT_Att) as lg_ft_pct FROM Projections),
            PlayerImpact AS (SELECT pr.*, (pr.FG_Made - (la.lg_fg_pct * pr.FG_Att)) as fg_impact, (pr.FT_Made - (la.lg_ft_pct * pr.FT_Att)) as ft_impact FROM Projections pr CROSS JOIN LeagueAvg la),
            LeagueImpactStats AS (SELECT AVG(fg_impact) as avg_fg_imp, AVG(fg_impact*fg_impact) as sq_fg_imp, AVG(ft_impact) as avg_ft_imp, AVG(ft_impact*ft_impact) as sq_ft_imp, AVG(PTS*PTS) as sq_pts, AVG(REB*REB) as sq_reb, AVG(AST*AST) as sq_ast, AVG(STL*STL) as sq_stl, AVG(BLK*BLK) as sq_blk, AVG(Three_PM*Three_PM) as sq_3pm, AVG(TOV*TOV) as sq_tov FROM PlayerImpact),
            LeagueDeviations AS (SELECT SQRT(sq_pts - (la.avg_pts * la.avg_pts)) as std_pts, SQRT(sq_reb - (la.avg_reb * la.avg_reb)) as std_reb, SQRT(sq_ast - (la.avg_ast * la.avg_ast)) as std_ast, SQRT(sq_stl - (la.avg_stl * la.avg_stl)) as std_stl, SQRT(sq_blk - (la.avg_blk * la.avg_blk)) as std_blk, SQRT(sq_3pm - (la.avg_3pm * la.avg_3pm)) as std_3pm, SQRT(sq_tov - (la.avg_tov * la.avg_tov)) as std_tov, SQRT(sq_fg_imp - (avg_fg_imp * avg_fg_imp)) as std_fg, SQRT(sq_ft_imp - (avg_ft_imp * avg_ft_imp)) as std_ft FROM LeagueImpactStats CROSS JOIN LeagueAvg la)
            SELECT SUM((pi.PTS - la.avg_pts)/NULLIF(ld.std_pts,0)) as zPTS, SUM((pi.REB - la.avg_reb)/NULLIF(ld.std_reb,0)) as zREB, SUM((pi.AST - la.avg_ast)/NULLIF(ld.std_ast,0)) as zAST, SUM((pi.STL - la.avg_stl)/NULLIF(ld.std_stl,0)) as zSTL, SUM((pi.BLK - la.avg_blk)/NULLIF(ld.std_blk,0)) as zBLK, SUM((pi.Three_PM - la.avg_3pm)/NULLIF(ld.std_3pm,0)) as z3PM, SUM(((pi.TOV - la.avg_tov)/NULLIF(ld.std_tov,0))*-1) as zTOV, SUM((pi.fg_impact - lis.avg_fg_imp)/NULLIF(ld.std_fg,0)) as zFG, SUM((pi.ft_impact - lis.avg_ft_imp)/NULLIF(ld.std_ft,0)) as zFT FROM Draft_State ds JOIN PlayerImpact pi ON ds.Player_ID = pi.Player_ID CROSS JOIN LeagueAvg la CROSS JOIN LeagueImpactStats lis CROSS JOIN LeagueDeviations ld WHERE ds.Fantasy_Team = 'My Team'
        '''
        team_z = pd.read_sql(base_z_query, conn).iloc[0]
        weakest = team_z.nsmallest(3)
        cats = weakest.index.tolist()
        mapping = {'zPTS':'pts', 'zREB':'reb', 'zAST':'ast', 'zSTL':'stl', 'zBLK':'blk', 'z3PM':'3pm', 'zTOV':'tov', 'zFG':'fg', 'zFT':'ft'}
        
        for k in ['pts','reb','ast','stl','blk','3pm','tov','fg','ft']: w[k] = 1.0
        w[mapping[cats[0]]] = 0.0 # Hard punt
        w[mapping[cats[1]]] = 0.0 # Hard punt
        w[mapping[cats[2]]] = 0.5 # Soft punt
        
        auto_pivot_msg = f"<div style='background-color:#2d3748; padding:10px; border-radius:6px; font-size:12px; border-right:4px solid #ecc94b;'><b>הרובוט הפעיל פאנט:</b><br>מוחלט: {mapping[cats[0]].upper()}, {mapping[cats[1]].upper()}<br>חלקי: {mapping[cats[2]].upper()}</div>"

if auto_pivot_active:
    st.sidebar.markdown(auto_pivot_msg, unsafe_allow_html=True)
st.sidebar.markdown("<br><div style='font-size: 11px; color: #718096; margin-bottom: 10px;'>משקלים ידניים:</div>", unsafe_allow_html=True)

for i in range(0, len(punt_options), 2):
    cols = st.sidebar.columns(2)
    key1 = punt_options[i].lower().replace('%', '')
    val1 = cols[0].selectbox(f"{punt_options[i]}", [1.0, 0.75, 0.5, 0.25, 0.0], index=0, key=f"w_{key1}", disabled=auto_pivot_active)
    if not auto_pivot_active: w[key1] = val1
    
    if i + 1 < len(punt_options):
        key2 = punt_options[i+1].lower().replace('%', '')
        val2 = cols[1].selectbox(f"{punt_options[i+1]}", [1.0, 0.75, 0.5, 0.25, 0.0], index=0, key=f"w_{key2}", disabled=auto_pivot_active)
        if not auto_pivot_active: w[key2] = val2

st.sidebar.divider()

with st.sidebar.expander("📅 הגדרות לוז פלייאוף (מתקדם)"):
    schedule_file = st.file_uploader("קובץ לו\"ז (CSV)", type=["csv"])
    playoff_start = st.number_input("שבוע התחלה", min_value=1, max_value=30, value=22)
    playoff_end = st.number_input("שבוע סיום", min_value=1, max_value=30, value=24)

playoff_games_map = {}
if schedule_file is not None:
    try:
        sched_df = pd.read_csv(schedule_file)
        filtered = sched_df[(sched_df['weekNumber'] >= playoff_start) & (sched_df['weekNumber'] <= playoff_end)]
        def get_abbr(city, name): return TEAM_NAME_TO_ABBR.get(f"{str(city).strip()} {str(name).strip()}".upper(), f"{str(city).strip()} {str(name).strip()}".upper())
        filtered['away_abbr'] = filtered.apply(lambda row: get_abbr(row['awayTeamCity'], row['awayTeamName']), axis=1)
        filtered['home_abbr'] = filtered.apply(lambda row: get_abbr(row['homeTeamCity'], row['homeTeamName']), axis=1)
        playoff_games_map = filtered['away_abbr'].value_counts().add(filtered['home_abbr'].value_counts(), fill_value=0).astype(int).to_dict()
    except: pass

if not playoff_games_map: playoff_games_map = {t: 11 for t in TEAM_NAME_TO_ABBR.values()}

my_future_picks = []
for r in range(1, 16):
    p = (r - 1) * num_teams + st.session_state.my_draft_position if r % 2 != 0 else (r - 1) * num_teams + (num_teams - st.session_state.my_draft_position + 1)
    if p >= st.session_state.global_pick:
        my_future_picks.append(p)
next_my_pick = my_future_picks[0] if my_future_picks else st.session_state.global_pick + 99

# --- Main SQL & Data Engine ---
st.markdown("<h1 style='color: #f7fafc; margin-bottom: 0;'>🏀 Fantasy NBA <span style='color: #4299e1;'>H2H</span> Draft Tool</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #a0aec0; margin-bottom: 30px;'>Advanced 9-Cat Projections & Live Analytics Dashboard</p>", unsafe_allow_html=True)

query = f'''
WITH PlayerPool AS (
    SELECT p.Player_ID, p.Full_Name, p.Team, p.Position, pr.* 
    FROM Players p JOIN Projections pr ON p.Player_ID = pr.Player_ID 
    WHERE pr.MIN > 15 AND pr.Games_Played > 10 AND p.Player_ID NOT IN (SELECT Player_ID FROM Draft_State)
),
LeagueAvg AS (
    SELECT AVG(PTS) as avg_pts, AVG(REB) as avg_reb, AVG(AST) as avg_ast, AVG(STL) as avg_stl, AVG(BLK) as avg_blk, AVG(Three_PM) as avg_3pm, AVG(TOV) as avg_tov, SUM(FG_Made)/SUM(FG_Att) as lg_fg_pct, SUM(FT_Made)/SUM(FT_Att) as lg_ft_pct 
    FROM PlayerPool
),
PlayerImpact AS (
    SELECT pp.*, (pp.FG_Made - (la.lg_fg_pct * pp.FG_Att)) as fg_impact, (pp.FT_Made - (la.lg_ft_pct * pp.FT_Att)) as ft_impact 
    FROM PlayerPool pp CROSS JOIN LeagueAvg la
),
LeagueImpactStats AS (
    SELECT AVG(fg_impact) as avg_fg_imp, AVG(fg_impact*fg_impact) as sq_fg_imp, AVG(ft_impact) as avg_ft_imp, AVG(ft_impact*ft_impact) as sq_ft_imp, AVG(PTS*PTS) as sq_pts, AVG(REB*REB) as sq_reb, AVG(AST*AST) as sq_ast, AVG(STL*STL) as sq_stl, AVG(BLK*BLK) as sq_blk, AVG(Three_PM*Three_PM) as sq_3pm, AVG(TOV*TOV) as sq_tov 
    FROM PlayerImpact
),
LeagueDeviations AS (
    SELECT SQRT(sq_pts - (la.avg_pts * la.avg_pts)) as std_pts, SQRT(sq_reb - (la.avg_reb * la.avg_reb)) as std_reb, SQRT(sq_ast - (la.avg_ast * la.avg_ast)) as std_ast, SQRT(sq_stl - (la.avg_stl * la.avg_stl)) as std_stl, SQRT(sq_blk - (la.avg_blk * la.avg_blk)) as std_blk, SQRT(sq_3pm - (la.avg_3pm * la.avg_3pm)) as std_3pm, SQRT(sq_tov - (la.avg_tov * la.avg_tov)) as std_tov, SQRT(sq_fg_imp - (avg_fg_imp * avg_fg_imp)) as std_fg, SQRT(sq_ft_imp - (avg_ft_imp * avg_ft_imp)) as std_ft 
    FROM LeagueImpactStats CROSS JOIN LeagueAvg la
),
ZScores AS (
    SELECT pi.Player_ID, pi.Full_Name as Player, pi.Team, pi.Position, pi.Games_Played, pi.Rank as ADP,
           ((pi.PTS - la.avg_pts)/NULLIF(ld.std_pts,0))*{w['pts']} + ((pi.REB - la.avg_reb)/NULLIF(ld.std_reb,0))*{w['reb']} + ((pi.AST - la.avg_ast)/NULLIF(ld.std_ast,0))*{w['ast']} + ((pi.STL - la.avg_stl)/NULLIF(ld.std_stl,0))*{w['stl']} + ((pi.BLK - la.avg_blk)/NULLIF(ld.std_blk,0))*{w['blk']} + ((pi.Three_PM - la.avg_3pm)/NULLIF(ld.std_3pm,0))*{w['3pm']} + (((pi.TOV - la.avg_tov)/NULLIF(ld.std_tov,0))*-1)*{w['tov']} + ((pi.fg_impact - lis.avg_fg_imp)/NULLIF(ld.std_fg,0))*{w['fg']} + ((pi.ft_impact - lis.avg_ft_imp)/NULLIF(ld.std_ft,0))*{w['ft']} as Total_Value,
           ROUND(((pi.PTS - la.avg_pts)/NULLIF(ld.std_pts,0)), 2) as zPTS, ROUND(((pi.REB - la.avg_reb)/NULLIF(ld.std_reb,0)), 2) as zREB, ROUND(((pi.AST - la.avg_ast)/NULLIF(ld.std_ast,0)), 2) as zAST, ROUND(((pi.STL - la.avg_stl)/NULLIF(ld.std_stl,0)), 2) as zSTL, ROUND(((pi.BLK - la.avg_blk)/NULLIF(ld.std_blk,0)), 2) as zBLK, ROUND(((pi.Three_PM - la.avg_3pm)/NULLIF(ld.std_3pm,0)), 2) as z3PM, ROUND((((pi.TOV - la.avg_tov)/NULLIF(ld.std_tov,0))*-1), 2) as zTOV, ROUND(((pi.fg_impact - lis.avg_fg_imp)/NULLIF(ld.std_fg,0)), 2) as zFG, ROUND(((pi.ft_impact - lis.avg_ft_imp)/NULLIF(ld.std_ft,0)), 2) as zFT
    FROM PlayerImpact pi CROSS JOIN LeagueAvg la CROSS JOIN LeagueImpactStats lis CROSS JOIN LeagueDeviations ld
)
SELECT Player_ID, Player, Team, Position, Games_Played, ROUND(ADP, 0) as ADP, ROUND(Total_Value, 2) as Total_Value, zPTS, zREB, zAST, zSTL, zBLK, z3PM, zTOV, zFG, zFT FROM ZScores;
'''
df_board = pd.read_sql(query, conn)
df_board['PO_Games'] = df_board['Team'].str.strip().str.upper().map(playoff_games_map).fillna(11).astype(int)

# --- 2. מודל Tiers (מדרגות איכות לפי עמדה) ---
df_board = df_board.sort_values(by='Total_Value', ascending=False)
tier_map = {}
for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
    pos_players = df_board[df_board['Position'].str.contains(pos)].copy()
    current_tier = 1
    last_z = None
    for idx, row in pos_players.iterrows():
        if last_z is not None and (last_z - row['Total_Value']) > 0.75: # קפיצה מובהקת
            current_tier += 1
        tier_map[(row['Player_ID'], pos)] = current_tier
        last_z = row['Total_Value']

def get_player_tier(row):
    positions = [p.strip().upper() for p in str(row['Position']).split(',')]
    tiers = [tier_map.get((row['Player_ID'], p), 99) for p in positions]
    return min(tiers) if tiers else 1
df_board['Tier'] = df_board.apply(get_player_tier, axis=1)

# --- Survive Prob & Risk (מדד סיכון מבוסס משחקים) ---
def get_survive_status(adp):
    buffer = adp - next_my_pick
    if buffer >= 10: return "🟢"
    elif buffer >= -2: return "🟡"
    else: return "🔴"
df_board['Survive'] = df_board['ADP'].apply(get_survive_status)

def get_risk_status(gp):
    try:
        val = float(gp)
        if val >= 72: return "🟢" # Ironman
        elif val >= 65: return "🟡" # Load Management / Regular
        else: return "🔴" # Injury Prone
    except: return "🟡"
df_board['Risk'] = df_board['Games_Played'].apply(get_risk_status)

# --- SMART BOOSTS (Pos Penalty & Needs) ---
my_team_roster_check = pd.read_sql('SELECT p.Full_Name, p.Position, pr.PTS, pr.REB, pr.AST, pr.STL, pr.BLK, pr.Three_PM, pr.TOV, pr.FG_Made, pr.FG_Att, pr.FT_Made, pr.FT_Att FROM Draft_State ds JOIN Players p ON ds.Player_ID = p.Player_ID JOIN Projections pr ON p.Player_ID = pr.Player_ID WHERE ds.Fantasy_Team = "My Team"', conn)
num_my_players = len(my_team_roster_check)
if num_my_players > 0:
    my_pos_list = []
    for pos_str in my_team_roster_check['Position']: my_pos_list.extend([p.strip().upper() for p in str(pos_str).split(',')])
    pos_counts = {p: my_pos_list.count(p) for p in ['PG', 'SG', 'SF', 'PF', 'C']}
    def apply_pos_penalty(player_pos_str):
        base_p = [p for p in [p.strip().upper() for p in str(player_pos_str).split(',')] if p in pos_counts]
        if not base_p: return 0.0
        min_count = min([pos_counts.get(p, 0) for p in base_p])
        return -1.5 if min_count >= 4 else -0.5 if min_count == 3 else 0.0
    df_board['Total_Value'] += df_board['Position'].apply(apply_pos_penalty)

    l_avg_check = pd.read_sql('SELECT AVG(PTS) as PTS, AVG(REB) as REB, AVG(AST) as AST, AVG(STL) as STL, AVG(BLK) as BLK, AVG(Three_PM) as Three_PM, AVG(TOV) as TOV, SUM(FG_Made)/SUM(FG_Att) as lg_fg, SUM(FT_Made)/SUM(FT_Att) as lg_ft FROM Projections', conn).iloc[0]
    cat_to_z = {'PTS': 'zPTS', 'REB': 'zREB', 'AST': 'zAST', 'STL': 'zSTL', 'BLK': 'zBLK', 'Three_PM': 'z3PM', 'TOV': 'zTOV'}
    cat_to_w_key = {'PTS': 'pts', 'REB': 'reb', 'AST': 'ast', 'STL': 'stl', 'BLK': 'blk', 'Three_PM': '3pm', 'TOV': 'tov'}
    boost_series = pd.Series(0.0, index=df_board.index)
    
    for cat, w_key in cat_to_w_key.items():
        if w.get(w_key, 1.0) > 0:
            team_total = my_team_roster_check[cat].sum()
            expected_total = l_avg_check[cat] * num_my_players
            delta = team_total - expected_total if cat == 'TOV' else expected_total - team_total
            if delta > 0 and expected_total > 0:
                boost_series += df_board[cat_to_z.get(cat)].clip(lower=0) * min(delta / expected_total, 1.0) * w.get(w_key, 1.0) * 0.25
    df_board['Total_Value'] += boost_series

df_board['Total_Value'] = (df_board['Total_Value'] + ((df_board['PO_Games'] - 11) * 0.05)).round(2)

# רוחבי עמודות הותאמו ל-19 פריטים עכשיו
col_widths = [0.4, 1.8, 0.6, 0.4, 0.5, 0.5, 0.4, 0.4, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.2]
headers_map = [
    ("#", None), ("שחקן", "Player"), ("POS", "Position"), ("T", "Tier"), 
    ("ADP", "ADP"), ("סטטוס", "Survive"), ("🏥", "Risk"), ("PO", "PO_Games"), 
    ("Z", "Total_Value"), ("PTS", "zPTS"), ("REB", "zREB"), ("AST", "zAST"), 
    ("STL", "zSTL"), ("BLK", "zBLK"), ("3PM", "z3PM"), ("TOV", "zTOV"), 
    ("FG", "zFG"), ("FT", "zFT"), ("פעולה", None)
]

# פונקציה לעיבוד שורת שחקן לטבלה (כדי לא לשכפל קוד גם ל-Watchlist וגם ללוח הראשי)
def render_player_row(idx, row, is_wl=False):
    r_cols = st.columns(col_widths)
    r_cols[0].markdown(f"<div class='small-font center-text'>{idx + 1}</div>", unsafe_allow_html=True)
    r_cols[1].markdown(f"<div class='small-font left-text'><span class='player-name'>{row['Player']}</span><span class='player-meta'>({row['Team']})</span></div>", unsafe_allow_html=True)
    r_cols[2].markdown(f"<div class='small-font center-text'>{row['Position']}</div>", unsafe_allow_html=True)
    r_cols[3].markdown(f"<div class='small-font center-text' title='מדרגת איכות'><span class='tier-badge'>T{row['Tier']}</span></div>", unsafe_allow_html=True)
    r_cols[4].markdown(f"<div class='small-font center-text'>{int(row['ADP'])}</div>", unsafe_allow_html=True)
    r_cols[5].markdown(f"<div class='small-font center-text' title='סיכוי שיישאר לתור הבא'>{row['Survive']}</div>", unsafe_allow_html=True) 
    r_cols[6].markdown(f"<div class='small-font center-text' title='סיכון פציעה/מנוחות'>{row['Risk']}</div>", unsafe_allow_html=True) 
    r_cols[7].markdown(f"<div class='small-font center-text'>{int(row['PO_Games'])}</div>", unsafe_allow_html=True)
    r_cols[8].markdown(f"<div class='small-font center-text total-value'>{row['Total_Value']:.2f}</div>", unsafe_allow_html=True)
    r_cols[9].markdown(f"<div class='small-font center-text'>{color_z_score(row['zPTS'])}</div>", unsafe_allow_html=True)
    r_cols[10].markdown(f"<div class='small-font center-text'>{color_z_score(row['zREB'])}</div>", unsafe_allow_html=True)
    r_cols[11].markdown(f"<div class='small-font center-text'>{color_z_score(row['zAST'])}</div>", unsafe_allow_html=True)
    r_cols[12].markdown(f"<div class='small-font center-text'>{color_z_score(row['zSTL'])}</div>", unsafe_allow_html=True)
    r_cols[13].markdown(f"<div class='small-font center-text'>{color_z_score(row['zBLK'])}</div>", unsafe_allow_html=True)
    r_cols[14].markdown(f"<div class='small-font center-text'>{color_z_score(row['z3PM'])}</div>", unsafe_allow_html=True)
    r_cols[15].markdown(f"<div class='small-font center-text'>{color_z_score(row['zTOV'])}</div>", unsafe_allow_html=True) 
    r_cols[16].markdown(f"<div class='small-font center-text'>{color_z_score(row['zFG'])}</div>", unsafe_allow_html=True)
    r_cols[17].markdown(f"<div class='small-font center-text'>{color_z_score(row['zFT'])}</div>", unsafe_allow_html=True)
    with r_cols[18]:
        c1, c2 = st.columns([1, 1.5])
        is_starred = row['Player_ID'] in st.session_state.watchlist
        star_icon = "⭐" if is_starred else "☆"
        
        btn_key_prefix = "wl_" if is_wl else "main_"
        if is_wl:
            if c1.button("❌", key=f"{btn_key_prefix}rm_{row['Player_ID']}", use_container_width=True):
                st.session_state.watchlist.remove(row['Player_ID'])
                st.rerun()
        else:
            if c1.button(star_icon, key=f"{btn_key_prefix}star_{row['Player_ID']}", use_container_width=True):
                if is_starred: st.session_state.watchlist.remove(row['Player_ID'])
                else: st.session_state.watchlist.append(row['Player_ID'])
                st.rerun()
                
        if c2.button("נלקח", key=f"{btn_key_prefix}taken_{row['Player_ID']}", use_container_width=True, type="primary"):
            draft_player_to_db(row['Player'], current_picking_team, row['Player_ID'])
            st.rerun()
    st.markdown("<hr style='margin: 4px 0; border-color: rgba(255,255,255,0.05);'>", unsafe_allow_html=True)


# --- WATCHLIST SECTION ---
st.markdown("### ⭐ רשימת מעקב (Targets)")
wl_df = df_board[df_board['Player_ID'].isin(st.session_state.watchlist)].sort_values(by=st.session_state.sort_col_main, ascending=st.session_state.sort_asc_main)

if not wl_df.empty:
    container_height = min(250, max(120, len(wl_df) * 45 + 50))
    with st.container(height=container_height):
        fh_cols_wl = st.columns(col_widths)
        for i, (label, sort_col) in enumerate(headers_map):
            with fh_cols_wl[i]:
                st.markdown(f"<div style='font-size:11px; font-weight:700; color:#ecc94b; padding-top:4px; text-align:center;'>{label}</div>", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 0px 0 5px 0; border-color: rgba(236,201,75,0.3);'>", unsafe_allow_html=True)
        
        for idx, row in wl_df.reset_index().iterrows():
            render_player_row(idx, row, is_wl=True)
else:
    st.markdown("<div style='background-color: #1a202c; padding: 10px; border-radius: 6px; border: 1px dashed #2d3748; color: #718096; text-align: center; font-size: 13px;'>הרשימה ריקה. הוסף שחקנים מהטבלה למטה בעזרת כפתור ה-⭐ כדי לעקוב אחריהם בקלות.</div>", unsafe_allow_html=True)


# --- MAIN TABLE ---
st.markdown("---")
st.markdown(f"### 📊 הלוח המרכזי (Smart Projections)")
search_query = st.text_input("🔍 חיפוש שחקן / קבוצה / עמדה", "")
filtered_df = df_board[df_board['Player'].str.contains(search_query, case=False) | df_board['Team'].str.contains(search_query, case=False) | df_board['Position'].str.contains(search_query, case=False)] if search_query else df_board
df_sorted = filtered_df.sort_values(by=st.session_state.sort_col_main, ascending=st.session_state.sort_asc_main)

with st.container(height=500):
    fh_cols = st.columns(col_widths)
    for i, (label, sort_col) in enumerate(headers_map):
        with fh_cols[i]:
            if sort_col:
                arrow = " ↓" if st.session_state.sort_asc_main else " ↑" if st.session_state.sort_col_main == sort_col else ""
                if st.button(f"{label}{arrow}", key=f"sort_{sort_col}", use_container_width=True, help=f"מיין לפי {label}"):
                    st.session_state.sort_asc_main = not st.session_state.sort_asc_main if st.session_state.sort_col_main == sort_col else (True if sort_col == 'ADP' else False)
                    st.session_state.sort_col_main = sort_col
                    st.rerun()
            else:
                st.markdown(f"<div style='font-size:11px; font-weight:700; color:#a0aec0; padding-top:4px; text-align:center;'>{label}</div>", unsafe_allow_html=True)
                
    for idx, row in df_sorted.head(100).reset_index().iterrows():
        render_player_row(idx, row, is_wl=False)

st.markdown("---")

# --- DASHBOARD LAYOUT (2 Columns) ---
dash_left, dash_right = st.columns([5, 6])

with dash_left:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🧠 הצרכים של הקבוצה שלי (Team Fit)")
    my_team = pd.read_sql("SELECT SUM(PTS) as PTS, SUM(REB) as REB, SUM(AST) as AST, SUM(STL) as STL, SUM(BLK) as BLK, SUM(Three_PM) as Three_PM, SUM(TOV) as TOV FROM Draft_State ds JOIN Projections pr ON ds.Player_ID = pr.Player_ID WHERE ds.Fantasy_Team = 'My Team'", conn).iloc[0]
    l_avg = pd.read_sql("SELECT AVG(PTS) as PTS, AVG(REB) as REB, AVG(AST) as AST, AVG(STL) as STL, AVG(BLK) as BLK, AVG(Three_PM) as Three_PM, AVG(TOV) as TOV FROM Projections", conn).iloc[0]
    
    needs_html = "<div class='dash-card' style='display:flex; justify-content:space-between;'>"
    cats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM', 'TOV']
    for cat in cats:
        if len(my_team_roster_check) > 0:
            val = my_team[cat]
            diff = val - (l_avg[cat] * len(my_team_roster_check))
            is_inverse = (cat == 'TOV')
            is_positive = (diff < 0) if is_inverse else (diff > 0)
            color = "#48bb78" if is_positive else "#f56565"
            sign = "+" if diff > 0 else ""
        else:
            val, diff, color, sign = 0.0, 0.0, "#a0aec0", ""
            
        needs_html += f"<div style='text-align:center;'><div style='font-size:11px; color:#a0aec0; margin-bottom:5px;'>{cat}</div><div style='font-size:18px; font-weight:bold; color:#ffffff;'>{val:.1f}</div><div style='font-size:11px; font-weight:bold; color:{color}; margin-top:3px;'>{sign}{diff:.1f}</div></div>"
    needs_html += "</div>"
    st.markdown(needs_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🟢 הקבוצה שלי")
    my_team_roster = pd.read_sql('SELECT ds.Pick_Number as Pick, p.Full_Name as Player, p.Team, p.Position, pr.PTS, pr.AST, pr.REB FROM Draft_State ds JOIN Players p ON ds.Player_ID = p.Player_ID JOIN Projections pr ON p.Player_ID = pr.Player_ID WHERE ds.Fantasy_Team = "My Team" ORDER BY ds.Pick_Number', conn)
    if not my_team_roster.empty:
        st.dataframe(my_team_roster, use_container_width=True, hide_index=True)
        
        player_pool = [[p.strip().upper() for p in str(row['Position']).split(',')] for _, row in my_team_roster.iterrows()]
        unassigned = player_pool.copy()
        counts = {'PG': 0, 'SG': 0, 'SF': 0, 'PF': 0, 'C': 0, 'G': 0, 'F': 0, 'UTIL': 0, 'BN': 0}
        for s_pos in ['PG', 'SG', 'SF', 'PF', 'C']:
            for i, p_pos in enumerate(unassigned):
                if s_pos in p_pos: counts[s_pos] += 1; unassigned.pop(i); break
        for i, p_pos in enumerate(unassigned):
            if any(x in p_pos for x in ['PG', 'SG', 'G']): counts['G'] += 1; unassigned.pop(i); break
        for i, p_pos in enumerate(unassigned):
            if any(x in p_pos for x in ['SF', 'PF', 'F']): counts['F'] += 1; unassigned.pop(i); break
        while unassigned and counts['UTIL'] < 3: counts['UTIL'] += 1; unassigned.pop(0)
        while unassigned: counts['BN'] += 1; unassigned.pop(0)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📌 סטטוס סלוטים בסגל")
        slots_html = f"""
        <div class="dash-card" style="display: flex; gap: 10px; flex-wrap: wrap;">
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">PG</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['PG']>=1 else '#e2e8f0'};">{counts['PG']}/1</div></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">SG</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['SG']>=1 else '#e2e8f0'};">{counts['SG']}/1</div></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">SF</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['SF']>=1 else '#e2e8f0'};">{counts['SF']}/1</div></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">PF</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['PF']>=1 else '#e2e8f0'};">{counts['PF']}/1</div></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">C</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['C']>=1 else '#e2e8f0'};">{counts['C']}/1</div></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">G</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['G']>=1 else '#e2e8f0'};">{counts['G']}/1</div></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">F</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['F']>=1 else '#e2e8f0'};">{counts['F']}/1</div></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">UT</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['UTIL']>=3 else '#e2e8f0'};">{counts['UTIL']}/3</div></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 11px; color: #a0aec0; font-weight:bold;">BN</div><div style="font-size: 14px; font-weight: bold; color: {'#48bb78' if counts['BN']>=3 else '#e2e8f0'};">{counts['BN']}/3</div></div>
        </div>
        """
        st.markdown(slots_html, unsafe_allow_html=True)
    else:
        st.markdown("<div style='background-color: #1a202c; padding: 20px; border-radius: 8px; border: 1px dashed #2d3748; color: #718096; text-align: center; font-size: 13px;'>סגל ריק. בחר שחקן כדי להתחיל.</div>", unsafe_allow_html=True)


with dash_right:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### ⚔️ יחסי כוחות בליגה (Live H2H)")
    team_totals_query = '''
        SELECT ds.Fantasy_Team as "Team", COUNT(ds.Player_ID) as "Plyrs",
               ROUND(SUM(pr.PTS), 1) as PTS, ROUND(SUM(pr.REB), 1) as REB, ROUND(SUM(pr.AST), 1) as AST, 
               ROUND(SUM(pr.STL), 1) as STL, ROUND(SUM(pr.BLK), 1) as BLK, ROUND(SUM(pr.Three_PM), 1) as "3PM", 
               ROUND(SUM(pr.TOV), 1) as TOV
        FROM Draft_State ds JOIN Projections pr ON ds.Player_ID = pr.Player_ID GROUP BY ds.Fantasy_Team
    '''
    df_teams_actual = pd.read_sql(team_totals_query, conn)
    
    all_teams_list = ["My Team"] + [f"Team {i}" for i in range(1, int(num_teams) + 1) if i != st.session_state.my_draft_position]
    base_teams_df = pd.DataFrame({"Team": all_teams_list})
    
    if not df_teams_actual.empty:
        df_h2h = pd.merge(base_teams_df, df_teams_actual, on="Team", how="left").fillna(0)
    else:
        df_h2h = base_teams_df.copy()
        for cat in ["Plyrs", "PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV"]:
            df_h2h[cat] = 0
            
    df_h2h['Plyrs'] = df_h2h['Plyrs'].astype(int)
    df_h2h = df_h2h.sort_values(by="PTS", ascending=False)
    
    st.dataframe(df_h2h, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📍 מאגר שחקנים מול ביקוש (Heatmap)")
    heatmap_query = f'''
        WITH Available AS (SELECT Position FROM Players WHERE Player_ID NOT IN (SELECT Player_ID FROM Draft_State)),
        TotalAvail AS (SELECT COUNT(*) as cnt FROM Available),
        SlotsDefinition AS (
            SELECT 'PG' as slot, {num_teams} as demand UNION ALL SELECT 'SG', {num_teams} UNION ALL SELECT 'G', {num_teams} UNION ALL
            SELECT 'SF', {num_teams} UNION ALL SELECT 'PF', {num_teams} UNION ALL SELECT 'F', {num_teams} UNION ALL
            SELECT 'C', {num_teams} UNION ALL SELECT 'UTIL', {num_teams} * 3 UNION ALL SELECT 'BN', {num_teams} * 3
        )
        SELECT s.slot as סלוט, s.demand as "ביקוש (חסר)", 
            CASE WHEN s.slot IN ('UTIL', 'BN') THEN (SELECT cnt FROM TotalAvail) ELSE (SELECT COUNT(*) FROM Available WHERE Position LIKE '%' || s.slot || '%') END as "היצע (כשירים כעת)",
            ROUND(CASE WHEN s.slot IN ('UTIL', 'BN') THEN (SELECT cnt FROM TotalAvail) ELSE (SELECT COUNT(*) FROM Available WHERE Position LIKE '%' || s.slot || '%') END * 1.0 / NULLIF(s.demand, 1), 2) as "יחס נדירות"
        FROM SlotsDefinition s
    '''
    st.dataframe(pd.read_sql(heatmap_query, conn), use_container_width=True, hide_index=True)
