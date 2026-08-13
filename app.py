import streamlit as st
import pandas as pd
import sqlite3
import io

# הגדרת תצוגת האתר (רחבה)
st.set_page_config(page_title="Fantasy NBA Draft Board", layout="wide")

# טעינת בסיס הנתונים לזיכרון (Cache מונע קריאה מחדש של הקובץ בכל לחיצה)
@st.cache_resource
def setup_database():
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = conn.cursor()
    
    # בניית הטבלאות
    cursor.execute('CREATE TABLE Players (Player_ID INTEGER PRIMARY KEY AUTOINCREMENT, Full_Name TEXT UNIQUE NOT NULL, Team TEXT, Position TEXT, Injury_Status TEXT)')
    cursor.execute('''CREATE TABLE Projections (
        Player_ID INTEGER, Games_Played REAL, MIN REAL, PTS REAL, REB REAL, AST REAL, STL REAL, BLK REAL,
        Three_PM REAL, FG_Made REAL, FG_Att REAL, FT_Made REAL, FT_Att REAL, TOV REAL,
        FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID)
    )''')
    
    # קריאת הקובץ והזרקה ל-SQL
    with open('nba_data.csv', 'r', encoding='utf-8-sig') as f:
        lines = [line.strip().strip('"') for line in f.readlines()]
    df_raw = pd.read_csv(io.StringIO('\n'.join(lines)))
    df_raw.columns = df_raw.columns.str.strip()
    
    # ניקוי כפילויות לשחקנים שעברו בטרייד
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

# --- ממשק המשתמש ---
st.title("🏀 Fantasy NBA 9-Cat Draft Tool")

# תפריט צד לאסטרטגיית פאנט
st.sidebar.header("🎯 Punt Strategy")
st.sidebar.write("בחר קטגוריות שתרצה להתעלם מהן:")

punt_fg = st.sidebar.checkbox("Punt FG%")
punt_ft = st.sidebar.checkbox("Punt FT%")
punt_3pm = st.sidebar.checkbox("Punt 3PM")
punt_reb = st.sidebar.checkbox("Punt REB")
punt_ast = st.sidebar.checkbox("Punt AST")
punt_stl = st.sidebar.checkbox("Punt STL")
punt_blk = st.sidebar.checkbox("Punt BLK")
punt_pts = st.sidebar.checkbox("Punt PTS")
punt_tov = st.sidebar.checkbox("Punt TOV")

# הגדרת המשקלים לשאילתה הדינמית (0 אם סומן כדי לאפס את השפעת הקטגוריה, 1 אם לא)
w_fg = 0 if punt_fg else 1
w_ft = 0 if punt_ft else 1
w_3pm = 0 if punt_3pm else 1
w_reb = 0 if punt_reb else 1
w_ast = 0 if punt_ast else 1
w_stl = 0 if punt_stl else 1
w_blk = 0 if punt_blk else 1
w_pts = 0 if punt_pts else 1
w_tov = 0 if punt_tov else 1

# הרצת ה-SQL הדינמי עם משקולות הפאנט
query = f'''
WITH PuntStrategy AS (
    SELECT {w_pts} as w_pts, {w_reb} as w_reb, {w_ast} as w_ast, {w_stl} as w_stl, 
           {w_blk} as w_blk, {w_3pm} as w_3pm, {w_tov} as w_tov, {w_fg} as w_fg, {w_ft} as w_ft
),
PlayerPool AS (
    SELECT p.Player_ID, p.Full_Name, p.Team, pr.* 
    FROM Players p JOIN Projections pr ON p.Player_ID = pr.Player_ID
    WHERE pr.MIN > 15 AND pr.Games_Played > 10
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
LIMIT 150;
'''

# משיכת הנתונים למסגרת של פנדס
df_board = pd.read_sql(query, conn)

# הצגת הטבלה המעוצבת באתר
st.subheader("📊 Live Big Board")
st.dataframe(df_board, use_container_width=True, height=800)