import streamlit as st
import pandas as pd
import sqlite3
import io

# הגדרת תצוגת האתר (רחבה)
st.set_page_config(page_title="Fantasy NBA Draft Board", layout="wide")

# טעינת בסיס הנתונים לזיכרון
@st.cache_resource
def setup_database():
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('CREATE TABLE Players (Player_ID INTEGER PRIMARY KEY AUTOINCREMENT, Full_Name TEXT UNIQUE NOT NULL, Team TEXT, Position TEXT, Injury_Status TEXT)')
    cursor.execute('''CREATE TABLE Projections (
        Player_ID INTEGER, Games_Played REAL, MIN REAL, PTS REAL, REB REAL, AST REAL, STL REAL, BLK REAL,
        Three_PM REAL, FG_Made REAL, FG_Att REAL, FT_Made REAL, FT_Att REAL, TOV REAL,
        FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID)
    )''')
    
    with open('nba_data.csv', 'r', encoding='utf-8-sig') as f:
        lines = [line.strip().strip('"') for line in f.readlines()]
    df_raw = pd.read_csv(io.StringIO('\n'.join(lines)))
    df_raw.columns = df_raw.columns.str.strip()
    df_clean = df_raw.drop_duplicates(subset=['Player'], keep='first').copy()
    
    column_mapping = {
        'Player': 'Full_Name', 'Team': 'Team', 'Pos': 'Position', 'G': 'Games_Played',
        'MP': 'MIN', 'PTS': 'PTS', 'TRB': 'REB', 'AST': 'AST', 'STL': 'STL', 'BLK': 'BLK',
        '3P': 'Three_PM', 'FG': 'FG_Made', 'FGA': 'FG_Att', 'FT': 'FT_Made', 'FTA': 'FT_Att', 'TOV': 'TOV'
    }
    df_renamed = df_clean.rename(columns=column_mapping).fillna(0)
    df_renamed['Full_Name'] = df_renamed['Full_Name'].astype(str)
    
    for index, row in df_renamed.iterrows():
        cursor.execute('INSERT OR IGNORE INTO Players (Full_Name, Team, Position, Injury_Status) VALUES (?, ?, ?, ?)', 
                       (row['Full_Name'], str(row['Team']), str(row['Position']), 'Healthy'))
    
    players_db = pd.read_sql('SELECT Player_ID, Full_Name FROM Players', conn)
    df_merged = pd.merge(df_renamed, players_db, on='Full_Name', how='inner')
    
    cols_to_keep = ['Player_ID', 'Games_Played', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM', 'FG_Made', 'FG_Att', 'FT_Made', 'FT_Att', 'TOV']
    projections_df = df_merged[cols_to_keep]
    projections_df.to_sql('Projections', conn, if_exists='replace', index=False)
    
    return conn

conn = setup_database()
cursor = conn.cursor()

# יצירת טבלת מעקב דראפט בזיכרון אם לא קיימת
cursor.execute('''
CREATE TABLE IF NOT EXISTS Draft_State (
    Draft_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Player_ID INTEGER,
    Fantasy_Team TEXT,
    Pick_Number INTEGER,
    FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID)
)
''')
conn.commit()

# --- ממשק משתמש (Streamlit UI) ---
st.title("🏀 Fantasy NBA 9-Cat Draft Tool")

# תפריט צד: אסטרטגיית פאנט
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

w_fg = 0 if punt_fg else 1
w_ft = 0 if punt_ft else 1
w_3pm = 0 if punt_3pm else 1
w_reb = 0 if punt_reb else 1
w_ast = 0 if punt_ast else 1
w_stl = 0 if punt_stl else 1
w_blk = 0 if punt_blk else 1
w_pts = 0 if punt_pts else 1
w_tov = 0 if punt_tov else 1

# --- אזור ניהול בחירות דראפט (Live Draft Control) ---
st.sidebar.markdown("---")
st.sidebar.header("🛠️ Live Draft Control")

available_players_df = pd.read_sql('''
    SELECT Full_Name FROM Players 
    WHERE Player_ID NOT IN (SELECT Player_ID FROM Draft_State)
    ORDER BY Full_Name
''', conn)

selected_player = st.sidebar.selectbox("בחר שחקן לתפוס:", available_players_df['Full_Name'])

# יצירת רשימה של 12 קבוצות בליגה (הקבוצה שלך ועוד 11 יריבים)
league_teams = ["My Team"] + [f"Team {i}" for i in range(1, 12)]
draft_team = st.sidebar.selectbox("לאיזו קבוצה שייכת הבחירה?", league_teams)

if st.sidebar.button("בחר שחקן (Draft Player)"):
    # תיקון באג האפסים: וידוא שמספר הבחירה הוא מספר שלם נקי (Scalar) בלבד
    res = cursor.execute('SELECT COUNT(*) FROM Draft_State').fetchone()
    next_pick = int(res[0]) + 1 if res else 1
    
    cursor.execute('''
        INSERT INTO Draft_State (Player_ID, Fantasy_Team, Pick_Number)
        SELECT Player_ID, ?, ? FROM Players WHERE Full_Name = ?
    ''', (draft_team, next_pick, selected_player))
    conn.commit()
    st.rerun()

if st.sidebar.button("אפס את כל הדראפט"):
    cursor.execute('DELETE FROM Draft_State')
    conn.commit()
    st.rerun()

# --- שאילתת המאסטר ללוח החי ---
query = f'''
WITH PuntStrategy AS (
    SELECT {w_pts} as w_pts, {w_reb} as w_reb, {w_ast} as w_ast, {w_stl} as w_stl, 
           {w_blk} as w_blk, {w_3pm} as w_3pm, {w_tov} as w_tov, {w_fg} as w_fg, {w_ft} as w_ft
),
PlayerPool AS (
    SELECT p.Player_ID, p.Full_Name, p.Team, pr.* 
    FROM Players p JOIN Projections pr ON p.Player_ID = pr.Player_ID
    WHERE pr.MIN > 15 AND pr.Games_Played > 10
      AND p.Player_ID NOT IN (SELECT Player_ID FROM Draft_State)
),
LeagueAvg AS (
    SELECT AVG(PTS) as avg_pts, AVG(REB) as avg_reb, AVG(AST) as avg_ast, AVG(STL) as avg_stl, 
           AVG(BLK) as avg_blk, AVG(Three_PM) as avg_3pm, AVG(TOV) as avg_tov, 
           SUM(FG_Made)/SUM(FG_Att) as lg_fg_pct, SUM(FT_Made)/SUM(FT_Att) as lg_ft_pct
    FROM PlayerPool
),
PlayerImpact AS (
    SELECT pp.*, (pp.FG_Made - (la.lg_fg_pct * pp.FG_Att)) as fg_impact, (pp.FT_Made - (la.lg_ft_pct * pp.FT_Att)) as ft_impact
    FROM PlayerPool pp CROSS JOIN LeagueAvg la
),
LeagueImpactStats AS (
    SELECT AVG(fg_impact) as avg_fg_imp, AVG(fg_impact * fg_impact) as sq_fg_imp,
           AVG(ft_impact) as avg_ft_imp, AVG(ft_impact * ft_impact) as sq_ft_imp,
           AVG(PTS*PTS) as sq_pts, AVG(REB*REB) as sq_reb, AVG(AST*AST) as sq_ast,
           AVG(STL*STL) as sq_stl, AVG(BLK*BLK) as sq_blk, AVG(Three_PM*Three_PM) as sq_3pm, AVG(TOV*TOV) as sq_tov
    FROM PlayerImpact
),
LeagueDeviations AS (
    SELECT SQRT(sq_pts - (la.avg_pts * la.avg_pts)) as std_pts, SQRT(sq_reb - (la.avg_reb * la.avg_reb)) as std_reb,
           SQRT(sq_ast - (la.avg_ast * la.avg_ast)) as std_ast, SQRT(sq_stl - (la.avg_stl * la.avg_stl)) as std_stl,
           SQRT(sq_blk - (la.avg_blk * la.avg_blk)) as std_blk, SQRT(sq_3pm - (la.avg_3pm * la.avg_3pm)) as std_3pm,
           SQRT(sq_tov - (la.avg_tov * la.avg_tov)) as std_tov, SQRT(sq_fg_imp - (avg_fg_imp * avg_fg_imp)) as std_fg,
           SQRT(sq_ft_imp - (avg_ft_imp * avg_ft_imp)) as std_ft
    FROM LeagueImpactStats CROSS JOIN LeagueAvg la
),
ZScores AS (
    SELECT pi.Full_Name as Player, pi.Team,
           ((pi.PTS - la.avg_pts) / NULLIF(ld.std_pts, 0)) * ps.w_pts as zPTS,
           ((pi.REB - la.avg_reb) / NULLIF(ld.std_reb, 0)) * ps.w_reb as zREB,
           ((pi.AST - la.avg_ast) / NULLIF(ld.std_ast, 0)) * ps.w_ast as zAST,
           ((pi.STL - la.avg_stl) / NULLIF(ld.std_stl, 0)) * ps.w_stl as zSTL,
           ((pi.BLK - la.avg_blk) / NULLIF(ld.std_blk, 0)) * ps.w_blk as zBLK,
           ((pi.Three_PM - la.avg_3pm) / NULLIF(ld.std_3pm, 0)) * ps.w_3pm as z3PM,
           (((pi.TOV - la.avg_tov) / NULLIF(ld.std_tov, 0)) * -1) * ps.w_tov as zTOV,
           ((pi.fg_impact - lis.avg_fg_imp) / NULLIF(ld.std_fg, 0)) * ps.w_fg as zFG,
           ((pi.ft_impact - lis.avg_ft_imp) / NULLIF(ld.std_ft, 0)) * ps.w_ft as zFT
    FROM PlayerImpact pi CROSS JOIN LeagueAvg la CROSS JOIN LeagueImpactStats lis CROSS JOIN LeagueDeviations ld CROSS JOIN PuntStrategy ps
)
SELECT Player, Team, 
       ROUND(zPTS + zREB + zAST + zSTL + zBLK + z3PM + zTOV + zFG + zFT, 2) as Total_Value,
       ROUND(zPTS, 2) as zPTS, ROUND(zREB, 2) as zREB, ROUND(zAST, 2) as zAST, 
       ROUND(zSTL, 2) as zSTL, ROUND(zBLK, 2) as zBLK, ROUND(z3PM, 2) as z3PM, 
       ROUND(zFG, 2) as zFG, ROUND(zFT, 2) as zFT, ROUND(zTOV, 2) as zTOV
FROM ZScores
ORDER BY Total_Value DESC
LIMIT 100;
'''

df_board = pd.read_sql(query, conn)

# הצגת הלוח החי
st.subheader("📊 Live Big Board (Available Players)")
st.dataframe(df_board, use_container_width=True, height=500)

# הצגת הקבוצה שלי
st.subheader("🟢 My Team Roster")
my_team_df = pd.read_sql('''
    SELECT ds.Pick_Number as Pick, p.Full_Name as Player, p.Team, pr.PTS, pr.AST, pr.REB
    FROM Draft_State ds
    JOIN Players p ON ds.Player_ID = p.Player_ID
    JOIN Projections pr ON p.Player_ID = pr.Player_ID
    WHERE ds.Fantasy_Team = 'My Team'
    ORDER BY ds.Pick_Number
''', conn)
st.dataframe(my_team_df, use_container_width=True, height=200)

# --- המשך קוד app.py ---

# פונקציה לניתוח צרכי הקבוצה בזמן אמת
def display_team_needs(conn):
    st.subheader("🧠 Team Needs & Fit Analysis")
    
    # נתונים של הקבוצה שלי
    my_team_stats = pd.read_sql('''
        SELECT SUM(pr.PTS) as PTS, SUM(pr.REB) as REB, SUM(pr.AST) as AST, 
               SUM(pr.STL) as STL, SUM(pr.BLK) as BLK, SUM(pr.Three_PM) as Three_PM
        FROM Draft_State ds
        JOIN Projections pr ON ds.Player_ID = pr.Player_ID
        WHERE ds.Fantasy_Team = 'My Team'
    ''', conn)
    
    # חישוב ממוצע ליגה למספר השחקנים שנבחרו (הערכה)
    num_players = pd.read_sql("SELECT COUNT(*) FROM Draft_State WHERE Fantasy_Team = 'My Team'", conn).iloc[0,0]
    
    if num_players > 0:
        # כאן אנחנו משווים את סך הקטגוריות שלך לממוצע הליגה המצופה עבור מספר השחקנים שיש לך
        # זה נותן לך אינדיקציה אם אתה מעל או מתחת לממוצע בכל קטגוריה
        st.write(f"רוסטר נוכחי: {num_players} שחקנים.")
        
        # תצוגת מדדים (צבע ירוק לחיזוק, אדום לחולשה)
        cols = st.columns(6)
        metrics = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'Three_PM']
        
        for i, metric in enumerate(metrics):
            val = my_team_stats[metric].iloc[0]
            # זהו חישוב פשוט - אפשר לשכלל אותו מול ממוצע הליגה
            cols[i].metric(label=metric, value=round(val, 1))
    else:
        st.info("עדיין לא בחרת שחקנים לקבוצה שלך.")

# קרא לפונקציה הזו אחרי הצגת הלוח
display_team_needs(conn)
