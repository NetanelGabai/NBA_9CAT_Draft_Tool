import streamlit as st
import pandas as pd
import sqlite3
import io

st.set_page_config(page_title="Fantasy NBA Draft Tool", layout="wide")

if 'my_current_pick' not in st.session_state:
    st.session_state.my_current_pick = 1

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
        'Rk': 'Rank',
        'Player': 'Full_Name', 
        'Team': 'Team', 
        'Pos': 'Position', 
        'G': 'Games_Played',
        'MP': 'MIN', 
        'PTS': 'PTS', 
        'TRB': 'REB', 
        'AST': 'AST', 
        'STL': 'STL', 
        'BLK': 'BLK',
        '3P': 'Three_PM', 
        'FG': 'FG_Made', 
        'FGA': 'FG_Att', 
        'FT': 'FT_Made', 
        'FTA': 'FT_Att', 
        'TOV': 'TOV'
    }
    df_renamed = df_clean.rename(columns=column_mapping).fillna(0)
    df_renamed['Full_Name'] = df_renamed['Full_Name'].astype(str)
    df_renamed['Rank'] = pd.to_numeric(df_renamed['Rank'], errors='coerce').fillna(999)
    df_renamed['Position'] = df_renamed['Position'].astype(str)
    
    for index, row in df_renamed.iterrows():
        cursor.execute('INSERT OR IGNORE INTO Players (Full_Name, Team, Position, Injury_Status) VALUES (?, ?, ?, ?)', 
                       (row['Full_Name'], str(row['Team']), str(row['Position']), 'Healthy'))
    
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

def get_next_snake_pick(current_p, T):
    R = ((current_p - 1) // T) + 1
    if R % 2 != 0:
        s = ((current_p - 1) // T) + 1
    else:
        s = T - ((current_p - 1) // T)
    
    next_R = R + 1
    if next_R % 2 != 0:
        next_p = (next_R - 1) * T + s
    else:
        next_p = next_R * T - s + 1
    return next_p

# פונקציית עזר לביצוע בחירת שחקן למסד הנתונים
def draft_player_to_db(player_name, team_name):
    pick_to_save = st.session_state.my_current_pick
    cursor.execute('INSERT INTO Draft_State (Player_ID, Fantasy_Team, Pick_Number) SELECT Player_ID, ?, ? FROM Players WHERE Full_Name = ?', (team_name, int(pick_to_save), player_name))
    conn.commit()
    if team_name == "My Team":
        st.session_state.my_current_pick = get_next_snake_pick(st.session_state.my_current_pick, num_teams)

# --- UI Sidebar ---
st.sidebar.header("🎯 Punt Strategy")
punt_fg = st.sidebar.checkbox("Punt FG%")
punt_ft = st.sidebar.checkbox("Punt FT%")
punt_3pm = st.sidebar.checkbox("Punt 3PM")
punt_reb = st.sidebar.checkbox("Punt REB")
punt_ast = st.sidebar.checkbox("Punt AST")
punt_stl = st.sidebar.checkbox("Punt STL")
punt_blk = st.sidebar.checkbox("Punt BLK")
punt_pts = st.sidebar.checkbox("Punt PTS")
punt_tov = st.sidebar.checkbox("Punt TOV")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ הגדרות דראפט (Snake)")
num_teams = st.sidebar.number_input("מספר קבוצות בליגה", min_value=4, max_value=20, value=8)

st.sidebar.markdown(f"**הבחירה שלך בתור:** `{st.session_state.my_current_pick}`")

col_b1, col_b2, col_b3 = st.sidebar.columns(3)
if col_b1.button("-1 בחירה"):
    if st.session_state.my_current_pick > 1:
        st.session_state.my_current_pick -= 1
        st.rerun()
if col_b2.button("+1 בחירה"):
    st.session_state.my_current_pick = get_next_snake_pick(st.session_state.my_current_pick, num_teams)
    st.rerun()
if col_b3.button("איפוס מונה"):
    st.session_state.my_current_pick = 1
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("אפס דראפט מלא"):
    cursor.execute('DELETE FROM Draft_State')
    st.session_state.my_current_pick = 1
    conn.commit()
    st.rerun()

# --- Main Layout ---
st.title("🏀 Fantasy NBA 9-Cat Draft Tool")

w = {k: (0 if v else 1) for k, v in zip(['pts','reb','ast','stl','blk','3pm','tov','fg','ft'], [punt_pts, punt_reb, punt_ast, punt_stl, punt_blk, punt_3pm, punt_tov, punt_fg, punt_ft])}

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
           ROUND(pi.PTS, 1) as PTS, ROUND(pi.REB, 1) as REB, ROUND(pi.AST, 1) as AST, ROUND(pi.STL, 1) as STL, ROUND(pi.BLK, 1) as BLK, ROUND(pi.Three_PM, 1) as Three_PM, ROUND(pi.TOV, 1) as TOV
    FROM PlayerImpact pi CROSS JOIN LeagueAvg la CROSS JOIN LeagueImpactStats lis CROSS JOIN LeagueDeviations ld
)
SELECT Player_ID, Player, Team, Position, ROUND(ADP, 0) as ADP, ROUND(Total_Value, 2) as Total_Value,
       ROUND(ADP - {st.session_state.my_current_pick}, 0) as Reach_Score,
       PTS, REB, AST, STL, BLK, Three_PM, TOV
FROM ZScores
ORDER BY Total_Value DESC
LIMIT 50;
'''

df_board = pd.read_sql(query, conn)

# --- בחירה בין 2 סוגי טבלאות בדיוק כמו שביקשת ---
tab1, tab2 = st.tabs(["🔥 המלצות דראפט (Top Recommendations)", "📋 טבלת דירוג מלאה (Z-Score Rankings)"])

with tab1:
    st.subheader("המלצות דראפט חמות (לחץ כפתור לבחירה מהירה)")
    for index, row in df_board.head(15).iterrows():
        c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1, 1, 1, 1, 1, 1])
        c1.write(f"**{row['Player']}** ({row['Team']} - {row['Position']})")
        c2.write(f"ADP: {int(row['ADP'])}")
        c3.write(f"Value: {row['Total_Value']}")
        c4.write(f"Reach: {int(row['Reach_Score'])}")
        
        if c5.button("הוסף לסגל", key=f"rec_my_{row['Player_ID']}"):
            draft_player_to_db(row['Player'], "My Team")
            st.rerun()
        if c6.button("נלקח", key=f"rec_opp_{row['Player_ID']}"):
            draft_player_to_db(row['Player'], "Opponent")
            st.rerun()
        st.markdown("---")

with tab2:
    st.subheader("טבלת שחקנים מלאה עם פעולות מהירות")
    search_query = st.text_input("🔍 חיפוש שחקן / קבוצה / עמדה", "")
    
    filtered_df = df_board
    if search_query:
        filtered_df = df_board[df_board['Player'].str.contains(search_query, case=False, na=False) | 
                               df_board['Team'].str.contains(search_query, case=False, na=False) | 
                               df_board['Position'].str.contains(search_query, case=False, na=False)]
    
    for index, row in filtered_df.head(30).iterrows():
        c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 1, 1, 1, 1])
        c1.write(f"**{row['Player']}** ({row['Team']} - {row['Position']}) | PTS: {row['PTS']} | REB: {row['REB']} | AST: {row['AST']}")
        
        if c4.button("הוסף לסגל", key=f"full_my_{row['Player_ID']}"):
            draft_player_to_db(row['Player'], "My Team")
            st.rerun()
        if c5.button("נלקח", key=f"full_opp_{row['Player_ID']}"):
            draft_player_to_db(row['Player'], "Opponent")
            st.rerun()
        st.markdown("---")

# --- Team Analysis & Roster ---
st.subheader("🟢 My Team Roster")
my_team_roster = pd.read_sql('''
    SELECT ds.Pick_Number as Pick, p.Full_Name as Player, p.Team, p.Position, pr.PTS, pr.AST, pr.REB
    FROM Draft_State ds
    JOIN Players p ON ds.Player_ID = p.Player_ID
    JOIN Projections pr ON p.Player_ID = pr.Player_ID
    WHERE ds.Fantasy_Team = 'My Team'
    ORDER BY ds.Pick_Number
''', conn)
st.dataframe(my_team_roster, use_container_width=True, height=200)

# --- מעקב סלוטים נדרשים בסגנון קומפקטי ---
if not my_team_roster.empty:
    st.markdown("##### 📌 סלוטים נדרשים בסגל")
    player_pool = []
    for idx, row in my_team_roster.iterrows():
        pos_list = [p.strip().upper() for p in str(row['Position']).split(',')]
        player_pool.append(pos_list)
        
    unassigned = player_pool.copy()
    counts = {'PG': 0, 'SG': 0, 'SF': 0, 'PF': 0, 'C': 0, 'G': 0, 'F': 0, 'UTIL': 0, 'BN': 0}
    
    for s_pos in ['PG', 'SG', 'SF', 'PF', 'C']:
        found_idx = -1
        for i, p_pos in enumerate(unassigned):
            if s_pos in p_pos:
                found_idx = i
                break
        if found_idx != -1:
            counts[s_pos] += 1
            unassigned.pop(found_idx)
            
    for i, p_pos in enumerate(unassigned):
        if 'PG' in p_pos or 'SG' in p_pos or 'G' in p_pos:
            counts['G'] += 1
            unassigned.pop(i)
            break
            
    for i, p_pos in enumerate(unassigned):
        if 'SF' in p_pos or 'PF' in p_pos or 'F' in p_pos:
            counts['F'] += 1
            unassigned.pop(i)
            break
            
    while unassigned and counts['UTIL'] < 3:
        counts['UTIL'] += 1
        unassigned.pop(0)
        
    while unassigned:
        counts['BN'] += 1
        unassigned.pop(0)

    scol1, scol2, scol3, scol4, scol5, scol6, scol7, scol8 = st.columns(8)
    scol1.metric("PG", f"1/{counts['PG']}")
    scol2.metric("SG", f"1/{counts['SG']}")
    scol3.metric("SF", f"1/{counts['SF']}")
    scol4.metric("PF", f"1/{counts['PF']}")
    scol5.metric("C", f"1/{counts['C']}")
    scol6.metric("G", f"1/{counts['G']}")
    scol7.metric("F", f"1/{counts['F']}")
    scol8.metric("UTIL", f"3/{counts['UTIL']}")

st.subheader("🧠 Team Needs & Fit")
my_team = pd.read_sql("SELECT SUM(PTS) as PTS, SUM(REB) as REB, SUM(AST) as AST, SUM(STL) as STL, SUM(BLK) as BLK, SUM(Three_PM) as Three_PM, SUM(TOV) as TOV FROM Draft_State ds JOIN Projections pr ON ds.Player_ID = pr.Player_ID WHERE ds.Fantasy_Team = 'My Team'", conn).iloc[0]
l_avg = pd.read_sql("SELECT AVG(PTS) as PTS, AVG(REB) as REB, AVG(AST) as AST, AVG(STL) as STL, AVG(BLK) as BLK, AVG(Three_PM) as Three_PM, AVG(TOV) as TOV FROM Projections", conn).iloc[0]

num_players = conn.execute("SELECT COUNT(*) FROM Draft_State WHERE Fantasy_Team = 'My Team'").fetchone()[0]
if num_players > 0:
    cols = st.columns(7)
    for i, cat in enumerate(['PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM', 'TOV']):
        cols[i].metric(cat, round(my_team[cat], 1), delta=round(my_team[cat] - (l_avg[cat] * num_players), 1))
