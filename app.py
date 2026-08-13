import streamlit as st
import pandas as pd
import sqlite3
import io

st.set_page_config(page_title="Fantasy NBA Draft Tool", layout="wide")

# מילון תרגום מדויק לשמות המלאים שמופיעים בקובץ הלו"ז
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

if 'my_draft_position' not in st.session_state:
    st.session_state.my_draft_position = 1

if 'global_pick' not in st.session_state:
    st.session_state.global_pick = 1

@st.cache_resource
def setup_database():
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE Players (
        Player_ID INTEGER PRIMARY KEY AUTOINCREMENT, 
        Full_Name TEXT UNIQUE NOT NULL, 
        Team TEXT, 
        Position TEXT, 
        Injury_Status TEXT
    )''')
    cursor.execute('''CREATE TABLE Projections (
        Player_ID INTEGER, 
        Rank REAL,
        Games_Played REAL, 
        MIN REAL, 
        PTS REAL, 
        REB REAL, 
        AST REAL, 
        STL REAL, 
        BLK REAL,
        Three_PM REAL, 
        FG_Made REAL, 
        FG_Att REAL, 
        FT_Made REAL, 
        FT_Att REAL, 
        TOV REAL,
        FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID)
    )''')
    
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
    df_renamed['Full_Name'] = df_renamed['Full_Name'].astype(str)
    
    for index, row in df_renamed.iterrows():
        cursor.execute('INSERT OR IGNORE INTO Players (Full_Name, Team, Position, Injury_Status) VALUES (?, ?, ?, ?)', 
                       (row['Full_Name'], str(row['Team']).strip(), str(row['Position']), 'Healthy'))
    
    players_db = pd.read_sql('SELECT Player_ID, Full_Name FROM Players', conn)
    df_merged = pd.merge(df_renamed, players_db, on='Full_Name', how='inner')
    
    cols_to_keep = ['Player_ID', 'Rank', 'Games_Played', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM', 'FG_Made', 'FG_Att', 'FT_Made', 'FT_Att', 'TOV']
    projections_df = df_merged[cols_to_keep]
    projections_df.to_sql('Projections', conn, if_exists='replace', index=False)
    return conn

conn = setup_database()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS Draft_State (
    Draft_ID INTEGER PRIMARY KEY AUTOINCREMENT, 
    Player_ID INTEGER, 
    Fantasy_Team TEXT, 
    Pick_Number INTEGER, 
    FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID)
)''')
conn.commit()

def get_team_for_pick(p, T, my_pos):
    R = ((p - 1) // T) + 1
    if R % 2 != 0:
        pos = ((p - 1) % T) + 1
    else:
        pos = T - ((p - 1) % T)
    return "My Team" if pos == my_pos else f"Team {pos}"

def draft_player_to_db(player_name, team_name):
    pick_to_save = st.session_state.global_pick
    cursor.execute('INSERT INTO Draft_State (Player_ID, Fantasy_Team, Pick_Number) SELECT Player_ID, ?, ? FROM Players WHERE Full_Name = ?', (team_name, int(pick_to_save), player_name))
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
        away = filtered['away_abbr'].value_counts()
        home = filtered['home_abbr'].value_counts()
        total_games = away.add(home, fill_value=0).astype(int)
        playoff_games_map = total_games.to_dict()
        st.sidebar.success("הלו\"ז נטען בהצלחה!")
    except Exception as e:
        st.sidebar.error(f"שגיאה בעיבוד הקובץ: {e}")

if not playoff_games_map:
    playoff_games_map = {t: 11 for t in TEAM_NAME_TO_ABBR.values()}

# --- Draft Logic ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ הגדרות דראפט (Snake)")
num_teams = st.sidebar.number_input("מספר קבוצות בליגה", min_value=4, max_value=20, value=12)
chosen_pos = st.sidebar.number_input("הבחירה שלך בסבב (Draft Position)", min_value=1, max_value=int(num_teams), value=st.session_state.get('my_draft_position', 1))
st.session_state.my_draft_position = chosen_pos

current_picking_team = get_team_for_pick(st.session_state.global_pick, num_teams, st.session_state.my_draft_position)
st.sidebar.markdown(f"**בחירה נוכחית:** `{st.session_state.global_pick}` | **תור:** `{current_picking_team}`")

if st.sidebar.button("-1 בחירה") and st.session_state.global_pick > 1:
    st.session_state.global_pick -= 1; st.rerun()
if st.sidebar.button("+1 בחירה"):
    st.session_state.global_pick += 1; st.rerun()
if st.sidebar.button("אפס דראפט"):
    cursor.execute('DELETE FROM Draft_State'); st.session_state.global_pick = 1; conn.commit(); st.rerun()

# --- Main Layout ---
st.title("🏀 Fantasy NBA 9-Cat Draft Tool")

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
           ROUND(((pi.PTS - la.avg_pts)/NULLIF(ld.std_pts,0)), 2) as zPTS,
           ROUND(((pi.REB - la.avg_reb)/NULLIF(ld.std_reb,0)), 2) as zREB,
           ROUND(((pi.AST - la.avg_ast)/NULLIF(ld.std_ast,0)), 2) as zAST,
           ROUND(((pi.STL - la.avg_stl)/NULLIF(ld.std_stl,0)), 2) as zSTL,
           ROUND(((pi.BLK - la.avg_blk)/NULLIF(ld.std_blk,0)), 2) as zBLK,
           ROUND(((pi.Three_PM - la.avg_3pm)/NULLIF(ld.std_3pm,0)), 2) as z3PM,
           ROUND((((pi.TOV - la.avg_tov)/NULLIF(ld.std_tov,0))*-1), 2) as zTOV,
           ROUND(((pi.fg_impact - lis.avg_fg_imp)/NULLIF(ld.std_fg,0)), 2) as zFG,
           ROUND(((pi.ft_impact - lis.avg_ft_imp)/NULLIF(ld.std_ft,0)), 2) as zFT
    FROM PlayerImpact pi CROSS JOIN LeagueAvg la CROSS JOIN LeagueImpactStats lis CROSS JOIN LeagueDeviations ld
)
SELECT Player_ID, Player, Team, Position, ROUND(ADP, 0) as ADP, ROUND(Total_Value, 2) as Total_Value,
       ROUND(ADP - {st.session_state.global_pick}, 0) as Reach_Score,
       zPTS, zREB, zAST, zSTL, zBLK, z3PM, zTOV, zFG, zFT
FROM ZScores;
'''
df_board = pd.read_sql(query, conn)
df_board['Playoff_Games'] = df_board['Team'].str.strip().str.upper().map(playoff_games_map).fillna(11).astype(int)

# --- SMART RECOMMENDATIONS BOOST ---
my_team_roster_check = pd.read_sql('SELECT p.Full_Name, pr.PTS, pr.REB, pr.AST, pr.STL, pr.BLK, pr.Three_PM, pr.TOV FROM Draft_State ds JOIN Players p ON ds.Player_ID = p.Player_ID JOIN Projections pr ON p.Player_ID = pr.Player_ID WHERE ds.Fantasy_Team = "My Team"', conn)
if len(my_team_roster_check) > 0:
    l_avg_check = pd.read_sql('SELECT AVG(PTS) as PTS, AVG(REB) as REB, AVG(AST) as AST, AVG(STL) as STL, AVG(BLK) as BLK, AVG(Three_PM) as Three_PM, AVG(TOV) as TOV FROM Projections', conn).iloc[0]
    cat_to_z = {'PTS': 'zPTS', 'REB': 'zREB', 'AST': 'zAST', 'STL': 'zSTL', 'BLK': 'zBLK', 'Three_PM': 'z3PM', 'TOV': 'zTOV', 'FG': 'zFG', 'FT': 'zFT'}
    needs_boost = [z_col for cat, (z_col, w_key) in cat_to_z.items() if cat in ['PTS','REB','AST','STL','BLK','Three_PM','TOV','FG','FT'] and w.get(cat.lower().replace('%','')) == 1 and cat in my_team_roster_check.columns and my_team_roster_check[cat].sum() < (l_avg_check[cat] * len(my_team_roster_check))]
    if needs_boost: df_board['Total_Value'] += df_board[needs_boost].sum(axis=1) * 0.08
df_board['Total_Value'] += (df_board['Playoff_Games'] - 11) * 0.05
df_board['Total_Value'] = df_board['Total_Value'].round(2)

# --- 1. טבלת דירוג ראשית (עם כפתורים) ---
st.markdown("### 📋 טבלת דירוג מלאה")
df_sorted = df_board.sort_values(by=st.session_state.sort_col_main, ascending=st.session_state.sort_asc_main)

# תצוגה מותאמת אישית עם כפתורים (בלי Player_ID)
cols_to_show = ['Player', 'Team', 'Position', 'ADP', 'Playoff_Games', 'Total_Value', 'zPTS', 'zREB', 'zAST', 'zSTL', 'zBLK', 'z3PM', 'zTOV', 'zFG', 'zFT']
with st.container(height=500):
    header_cols = st.columns([1.5, 0.7, 0.6, 0.5, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.5])
    headers = ["שחקן", "Team", "POS", "ADP", "PO_Games", "Z", "PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FG", "FT", "פעולה"]
    for i, h in enumerate(headers): header_cols[i].markdown(f"**{h}**")
    
    for idx, row in df_sorted.head(100).iterrows():
        r_cols = st.columns([1.5, 0.7, 0.6, 0.5, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.5])
        r_cols[0].write(f"{row['Player']} ({row['Team']})")
        r_cols[1].write(row['Team'])
        r_cols[2].write(row['Position'])
        r_cols[3].write(int(row['ADP']))
        r_cols[4].write(int(row['Playoff_Games']))
        r_cols[5].write(row['Total_Value'])
        r_cols[6].write(row['zPTS'])
        r_cols[7].write(row['zREB'])
        r_cols[8].write(row['zAST'])
        r_cols[9].write(row['zSTL'])
        r_cols[10].write(row['zBLK'])
        r_cols[11].write(row['z3PM'])
        r_cols[12].write(row['zTOV'])
        r_cols[13].write(row['zFG'])
        r_cols[14].write(row['zFT'])
        
        with r_cols[15]:
            b1, b2 = st.columns(2)
            if b1.button("הוסף", key=f"my_{row['Player_ID']}"): draft_player_to_db(row['Player'], "My Team"); st.rerun()
            if b2.button("נלקח", key=f"opp_{row['Player_ID']}"): draft_player_to_db(row['Player'], current_picking_team); st.rerun()
        st.markdown("<hr style='margin: 2px 0;'>", unsafe_allow_html=True)

# --- 2. רוסטר וטבלאות נוספות ---
my_team_roster = pd.read_sql('SELECT ds.Pick_Number as Pick, p.Full_Name as Player, p.Team, p.Position FROM Draft_State ds JOIN Players p ON ds.Player_ID = p.Player_ID WHERE ds.Fantasy_Team = "My Team" ORDER BY ds.Pick_Number', conn)
st.subheader("🟢 My Team Roster")
st.dataframe(my_team_roster, use_container_width=True, hide_index=True)

st.subheader("🗓️ לוח דראפט ליגה מלא")
teams_order = ["My Team"] + [f"Team {i}" for i in range(1, num_teams + 1) if i != st.session_state.my_draft_position]
# (השארנו את ה-Draft Grid וה-Heatmap כמו שהיו)
