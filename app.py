import streamlit as st
import pandas as pd
import sqlite3
import io

st.set_page_config(page_title="Fantasy NBA Draft Tool", layout="wide")

# מילון תרגום מדויק לשמות המלאים
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

def draft_player_to_db(player_name, team_name):
    cursor.execute('INSERT INTO Draft_State (Player_ID, Fantasy_Team, Pick_Number) SELECT Player_ID, ?, ? FROM Players WHERE Full_Name = ?', (team_name, int(st.session_state.global_pick), player_name))
    conn.commit()
    st.session_state.global_pick += 1

# --- UI Sidebar ---
st.sidebar.header("🎯 אסטרטגיית פאנטים רכה")
st.sidebar.markdown("<div style='font-size: 11px; color: gray; margin-bottom: 10px;'>1.0 = רגיל | 0.5 = פאנט חלקי | 0.0 = פאנט מוחלט</div>", unsafe_allow_html=True)
punt_options = ["FG%", "FT%", "3PM", "REB", "AST", "STL", "BLK", "PTS", "TOV"]
w = {}
for i in range(0, len(punt_options), 2):
    cols = st.sidebar.columns(2)
    key1 = punt_options[i].lower().replace('%', '')
    w[key1] = cols[0].selectbox(f"{punt_options[i]}", [1.0, 0.75, 0.5, 0.25, 0.0], index=0, key=f"w_{key1}")
    if i + 1 < len(punt_options):
        key2 = punt_options[i+1].lower().replace('%', '')
        w[key2] = cols[1].selectbox(f"{punt_options[i+1]}", [1.0, 0.75, 0.5, 0.25, 0.0], index=0, key=f"w_{key2}")

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
        def get_abbr(city, name): return TEAM_NAME_TO_ABBR.get(f"{str(city).strip()} {str(name).strip()}".upper(), f"{str(city).strip()} {str(name).strip()}".upper())
        filtered['away_abbr'] = filtered.apply(lambda row: get_abbr(row['awayTeamCity'], row['awayTeamName']), axis=1)
        filtered['home_abbr'] = filtered.apply(lambda row: get_abbr(row['homeTeamCity'], row['homeTeamName']), axis=1)
        playoff_games_map = filtered['away_abbr'].value_counts().add(filtered['home_abbr'].value_counts(), fill_value=0).astype(int).to_dict()
    except: pass

if not playoff_games_map: playoff_games_map = {t: 11 for t in TEAM_NAME_TO_ABBR.values()}

st.sidebar.markdown("---")
st.sidebar.header("⚙️ הגדרות דראפט (Snake)")
num_teams = st.sidebar.number_input("מספר קבוצות בליגה", min_value=4, max_value=20, value=12)
st.session_state.my_draft_position = st.sidebar.number_input("הבחירה שלך בסבב (Draft Position)", min_value=1, max_value=int(num_teams), value=st.session_state.get('my_draft_position', 1))

current_picking_team = get_team_for_pick(st.session_state.global_pick, num_teams, st.session_state.my_draft_position)
st.sidebar.markdown(f"**בחירה נוכחית:** `{st.session_state.global_pick}` | **תור:** `{current_picking_team}`")

col_b1, col_b2, col_b3 = st.sidebar.columns(3)
if col_b1.button("-1 בחירה") and st.session_state.global_pick > 1: st.session_state.global_pick -= 1; st.rerun()
if col_b2.button("+1 בחירה"): st.session_state.global_pick += 1; st.rerun()
if col_b3.button("איפוס"): cursor.execute('DELETE FROM Draft_State'); st.session_state.global_pick = 1; conn.commit(); st.rerun()

# --- חישוב תורות עתידיים לטובת מודל ההישרדות ---
my_future_picks = []
for r in range(1, 16):
    p = (r - 1) * num_teams + st.session_state.my_draft_position if r % 2 != 0 else (r - 1) * num_teams + (num_teams - st.session_state.my_draft_position + 1)
    if p >= st.session_state.global_pick:
        my_future_picks.append(p)
next_my_pick = my_future_picks[0] if my_future_picks else st.session_state.global_pick + 99

# --- Main SQL ---
st.title("🏀 Fantasy NBA H2H 9-Cat Draft Tool")

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
    SELECT pi.Player_ID, pi.Full_Name as Player, pi.Team, pi.Position, pi.Rank as ADP,
           ((pi.PTS - la.avg_pts)/NULLIF(ld.std_pts,0))*{w['pts']} + ((pi.REB - la.avg_reb)/NULLIF(ld.std_reb,0))*{w['reb']} + ((pi.AST - la.avg_ast)/NULLIF(ld.std_ast,0))*{w['ast']} + ((pi.STL - la.avg_stl)/NULLIF(ld.std_stl,0))*{w['stl']} + ((pi.BLK - la.avg_blk)/NULLIF(ld.std_blk,0))*{w['blk']} + ((pi.Three_PM - la.avg_3pm)/NULLIF(ld.std_3pm,0))*{w['3pm']} + (((pi.TOV - la.avg_tov)/NULLIF(ld.std_tov,0))*-1)*{w['tov']} + ((pi.fg_impact - lis.avg_fg_imp)/NULLIF(ld.std_fg,0))*{w['fg']} + ((pi.ft_impact - lis.avg_ft_imp)/NULLIF(ld.std_ft,0))*{w['ft']} as Total_Value,
           ROUND(((pi.PTS - la.avg_pts)/NULLIF(ld.std_pts,0)), 2) as zPTS, ROUND(((pi.REB - la.avg_reb)/NULLIF(ld.std_reb,0)), 2) as zREB, ROUND(((pi.AST - la.avg_ast)/NULLIF(ld.std_ast,0)), 2) as zAST, ROUND(((pi.STL - la.avg_stl)/NULLIF(ld.std_stl,0)), 2) as zSTL, ROUND(((pi.BLK - la.avg_blk)/NULLIF(ld.std_blk,0)), 2) as zBLK, ROUND(((pi.Three_PM - la.avg_3pm)/NULLIF(ld.std_3pm,0)), 2) as z3PM, ROUND((((pi.TOV - la.avg_tov)/NULLIF(ld.std_tov,0))*-1), 2) as zTOV, ROUND(((pi.fg_impact - lis.avg_fg_imp)/NULLIF(ld.std_fg,0)), 2) as zFG, ROUND(((pi.ft_impact - lis.avg_ft_imp)/NULLIF(ld.std_ft,0)), 2) as zFT
    FROM PlayerImpact pi CROSS JOIN LeagueAvg la CROSS JOIN LeagueImpactStats lis CROSS JOIN LeagueDeviations ld
)
SELECT Player_ID, Player, Team, Position, ROUND(ADP, 0) as ADP, ROUND(Total_Value, 2) as Total_Value, zPTS, zREB, zAST, zSTL, zBLK, z3PM, zTOV, zFG, zFT FROM ZScores;
'''
df_board = pd.read_sql(query, conn)
df_board['PO_Games'] = df_board['Team'].str.strip().str.upper().map(playoff_games_map).fillna(11).astype(int)

# --- מודל הישרדות (Survive Prob) ---
def get_survive_status(adp):
    buffer = adp - next_my_pick
    if buffer >= 10: return "🟢"
    elif buffer >= -2: return "🟡"
    else: return "🔴"
df_board['Survive'] = df_board['ADP'].apply(get_survive_status)

# --- SMART BOOSTS ---
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

# --- CSS Styling ---
st.markdown("""
    <style>
    .small-font { font-size: 13px !important; white-space: nowrap !important; padding-top: 6px; color: #f0f2f6; }
    .center-text { text-align: center; } .left-text { text-align: left; }
    div[data-testid="stScrollableContainer"] > div > div:first-child { position: sticky !important; top: 0 !important; z-index: 100 !important; background-color: var(--background-color) !important; border-bottom: 1px solid rgba(255,255,255,0.15) !important; padding-top: 5px !important; padding-bottom: 5px !important; }
    section[data-testid="stMain"] button[kind="secondary"] { background-color: transparent !important; border: none !important; box-shadow: none !important; font-size: 12px !important; font-weight: bold !important; color: #9fb3c8 !important; padding: 0 !important; margin: 0 !important; justify-content: center !important; }
    section[data-testid="stMain"] button[kind="secondary"]:hover { color: #ffffff !important; background-color: transparent !important; }
    section[data-testid="stMain"] button[kind="primary"] { background-color: #2b313e !important; border: 1px solid #4c566a !important; color: #ffffff !important; padding: 0px 8px !important; font-size: 12px !important; min-height: 26px !important; height: 26px !important; border-radius: 4px !important; line-height: 1 !important; }
    section[data-testid="stMain"] button[kind="primary"]:hover { border-color: #e2e8f0 !important; background-color: #4c566a !important; }
    [data-testid="column"] { padding-left: 0.15rem !important; padding-right: 0.15rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- Main Table ---
st.markdown(f"### 📋 לוח דירוג (תור נוכחי: {st.session_state.global_pick} | התור הבא שלך: {next_my_pick})")
search_query = st.text_input("🔍 חיפוש שחקן / קבוצה / עמדה", "")
filtered_df = df_board[df_board['Player'].str.contains(search_query, case=False) | df_board['Team'].str.contains(search_query, case=False) | df_board['Position'].str.contains(search_query, case=False)] if search_query else df_board
df_sorted = filtered_df.sort_values(by=st.session_state.sort_col_main, ascending=st.session_state.sort_asc_main)

col_widths = [0.4, 1.8, 0.6, 0.5, 0.8, 0.5, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.8]
headers_map = [("#", None), ("שחקן", "Player"), ("POS", "Position"), ("ADP", "ADP"), ("סטטוס", "Survive"), ("PO", "PO_Games"), ("Z", "Total_Value"), ("PTS", "zPTS"), ("REB", "zREB"), ("AST", "zAST"), ("STL", "zSTL"), ("BLK", "zBLK"), ("3PM", "z3PM"), ("TOV", "zTOV"), ("FG", "zFG"), ("FT", "zFT"), ("פעולה", None)]

with st.container(height=450):
    fh_cols = st.columns(col_widths)
    for i, (label, sort_col) in enumerate(headers_map):
        with fh_cols[i]:
            if sort_col:
                arrow = " ↓" if st.session_state.sort_asc_main else " ↑" if st.session_state.sort_col_main == sort_col else ""
                if st.button(f"{label}{arrow}", key=f"sort_{sort_col}", use_container_width=True):
                    st.session_state.sort_asc_main = not st.session_state.sort_asc_main if st.session_state.sort_col_main == sort_col else (True if sort_col == 'ADP' else False)
                    st.session_state.sort_col_main = sort_col
                    st.rerun()
            else:
                st.markdown(f"<div style='font-size:12px; font-weight:bold; color:#9fb3c8; padding-top:4px; text-align:center;'>{label}</div>", unsafe_allow_html=True)
                
    for idx, row in df_sorted.head(100).reset_index().iterrows():
        r_cols = st.columns(col_widths)
        r_cols[0].markdown(f"<div class='small-font center-text'>{idx + 1}</div>", unsafe_allow_html=True)
        r_cols[1].markdown(f"<div class='small-font left-text'>{row['Player']} ({row['Team']})</div>", unsafe_allow_html=True)
        r_cols[2].markdown(f"<div class='small-font center-text'>{row['Position']}</div>", unsafe_allow_html=True)
        r_cols[3].markdown(f"<div class='small-font center-text'>{int(row['ADP'])}</div>", unsafe_allow_html=True)
        r_cols[4].markdown(f"<div class='small-font center-text'>{row['Survive']}</div>", unsafe_allow_html=True) # עמודת סטטוס חדשה
        r_cols[5].markdown(f"<div class='small-font center-text'>{int(row['PO_Games'])}</div>", unsafe_allow_html=True)
        r_cols[6].markdown(f"<div class='small-font center-text'><b>{row['Total_Value']:.2f}</b></div>", unsafe_allow_html=True)
        r_cols[7].markdown(f"<div class='small-font center-text'>{row['zPTS']}</div>", unsafe_allow_html=True)
        r_cols[8].markdown(f"<div class='small-font center-text'>{row['zREB']}</div>", unsafe_allow_html=True)
        r_cols[9].markdown(f"<div class='small-font center-text'>{row['zAST']}</div>", unsafe_allow_html=True)
        r_cols[10].markdown(f"<div class='small-font center-text'>{row['zSTL']}</div>", unsafe_allow_html=True)
        r_cols[11].markdown(f"<div class='small-font center-text'>{row['zBLK']}</div>", unsafe_allow_html=True)
        r_cols[12].markdown(f"<div class='small-font center-text'>{row['z3PM']}</div>", unsafe_allow_html=True)
        r_cols[13].markdown(f"<div class='small-font center-text'>{row['zTOV']}</div>", unsafe_allow_html=True)
        r_cols[14].markdown(f"<div class='small-font center-text'>{row['zFG']}</div>", unsafe_allow_html=True)
        r_cols[15].markdown(f"<div class='small-font center-text'>{row['zFT']}</div>", unsafe_allow_html=True)
        with r_cols[16]:
            if st.button("נלקח", key=f"taken_{row['Player_ID']}", use_container_width=True, type="primary"):
                draft_player_to_db(row['Player'], current_picking_team)
                st.rerun()
        st.markdown("<hr style='margin: 4px 0; opacity: 0.1;'>", unsafe_allow_html=True)

# --- 2. Live H2H League Projections ---
st.markdown("---")
st.subheader("📊 כוח קבוצות בליגה (Live H2H Projections)")
team_totals_query = '''
    SELECT ds.Fantasy_Team as "קבוצה", COUNT(ds.Player_ID) as "שחקנים",
           ROUND(SUM(pr.PTS), 1) as PTS, ROUND(SUM(pr.REB), 1) as REB, ROUND(SUM(pr.AST), 1) as AST, 
           ROUND(SUM(pr.STL), 1) as STL, ROUND(SUM(pr.BLK), 1) as BLK, ROUND(SUM(pr.Three_PM), 1) as "3PM", 
           ROUND(SUM(pr.TOV), 1) as TOV
    FROM Draft_State ds JOIN Projections pr ON ds.Player_ID = pr.Player_ID GROUP BY ds.Fantasy_Team
'''
df_teams = pd.read_sql(team_totals_query, conn)
if not df_teams.empty:
    st.dataframe(df_teams, use_container_width=True, hide_index=True)
else:
    st.info("הטבלה תתעדכן ברגע שיתחילו להיבחר שחקנים בדראפט.")

# --- 3. סלוטים נדרשים בסגל ---
my_team_roster = pd.read_sql('SELECT ds.Pick_Number as Pick, p.Full_Name as Player, p.Team, p.Position, pr.PTS, pr.AST, pr.REB FROM Draft_State ds JOIN Players p ON ds.Player_ID = p.Player_ID JOIN Projections pr ON p.Player_ID = pr.Player_ID WHERE ds.Fantasy_Team = "My Team" ORDER BY ds.Pick_Number', conn)
if not my_team_roster.empty:
    st.markdown("##### 📌 סלוטים נדרשים בסגל")
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
    scol1, scol2, scol3, scol4, scol5, scol6, scol7, scol8, scol9 = st.columns(9)
    scol1.metric("PG", f"1/{counts['PG']}"); scol2.metric("SG", f"1/{counts['SG']}"); scol3.metric("SF", f"1/{counts['SF']}"); scol4.metric("PF", f"1/{counts['PF']}"); scol5.metric("C", f"1/{counts['C']}"); scol6.metric("G", f"1/{counts['G']}"); scol7.metric("F", f"1/{counts['F']}"); scol8.metric("UTIL", f"3/{counts['UTIL']}"); scol9.metric("BN", f"3/{counts['BN']}")

# --- 4. רוסטר הקבוצה שלך ---
st.subheader("🟢 My Team Roster")
st.dataframe(my_team_roster, use_container_width=True, height=200, hide_index=True)

# --- 5. Team Needs & Fit ---
st.subheader("🧠 Team Needs & Fit")
my_team = pd.read_sql("SELECT SUM(PTS) as PTS, SUM(REB) as REB, SUM(AST) as AST, SUM(STL) as STL, SUM(BLK) as BLK, SUM(Three_PM) as Three_PM, SUM(TOV) as TOV FROM Draft_State ds JOIN Projections pr ON ds.Player_ID = pr.Player_ID WHERE ds.Fantasy_Team = 'My Team'", conn).iloc[0]
l_avg = pd.read_sql("SELECT AVG(PTS) as PTS, AVG(REB) as REB, AVG(AST) as AST, AVG(STL) as STL, AVG(BLK) as BLK, AVG(Three_PM) as Three_PM, AVG(TOV) as TOV FROM Projections", conn).iloc[0]
if len(my_team_roster) > 0:
    cols = st.columns(7)
    for i, cat in enumerate(['PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM', 'TOV']):
        val = my_team[cat]; diff = val - (l_avg[cat] * len(my_team_roster))
        cols[i].metric(cat, round(val, 1), delta=round(diff, 1), delta_color="inverse" if cat == 'TOV' else "normal")
else:
    cols = st.columns(7)
    for i, cat in enumerate(['PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM', 'TOV']): cols[i].metric(cat, 0.0, delta=0.0)

# --- 6. Positional Heatmap ---
st.subheader("📍 Positional Heatmap (עומק מאגר מול ביקוש)")
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
st.dataframe(pd.read_sql(heatmap_query, conn), use_container_width=True, height=350, hide_index=True)
