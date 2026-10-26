export const TEAM_COLORS={'1':'#d85545','2':'#ce941d','3':'#3d7cbd','4':'#805bb6','5':'#218b74','6':'#b85790',unconfirmed:'#74818a'};
export const teamColor=team=>TEAM_COLORS[String(team?.key??team)]||TEAM_COLORS.unconfirmed;
