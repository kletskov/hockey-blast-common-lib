"""Initial migration.

Revision ID: c810b0c2307f
Revises: 
Create Date: 2024-12-10 19:16:26.865017

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c810b0c2307f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('divisions', schema=None) as batch_op:
        batch_op.alter_column('season_number',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.drop_constraint('divisions_league_number_season_number_level_key', type_='unique')

    with op.batch_alter_table('game_rosters', schema=None) as batch_op:
        batch_op.drop_constraint('game_rosters_game_id_team_id_human_id_key', type_='unique')
        batch_op.create_unique_constraint('_game_team_human_uc', ['game_id', 'team_id', 'human_id'])

    with op.batch_alter_table('goals', schema=None) as batch_op:
        batch_op.drop_constraint('goals_game_id_scoring_team_id_sequence_number_key', type_='unique')
        batch_op.create_unique_constraint('_goal_team_sequence_uc', ['game_id', 'scoring_team_id', 'sequence_number'])

    with op.batch_alter_table('human_aliases', schema=None) as batch_op:
        batch_op.drop_constraint('human_aliases_human_id_first_name_middle_name_last_name_key', type_='unique')
        batch_op.create_unique_constraint('_human_alias_uc', ['human_id', 'first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('humans', schema=None) as batch_op:
        batch_op.drop_constraint('humans_first_name_middle_name_last_name_key', type_='unique')

    with op.batch_alter_table('humans_in_levels', schema=None) as batch_op:
        batch_op.drop_constraint('humans_in_levels_levels_monthly_id_human_id_key', type_='unique')
        batch_op.create_unique_constraint('_levels_monthly_human_uc', ['levels_monthly_id', 'human_id'])

    with op.batch_alter_table('humans_in_tts', schema=None) as batch_op:
        batch_op.drop_constraint('humans_in_tts_human_id_tts_id_key', type_='unique')
        batch_op.create_unique_constraint('_human_tts_uc', ['human_id', 'tts_id'])

    with op.batch_alter_table('levels', schema=None) as batch_op:
        batch_op.create_unique_constraint('_level_name_uc', ['level_name'])

    with op.batch_alter_table('levels_monthly', schema=None) as batch_op:
        batch_op.drop_constraint('levels_monthly_year_month_league_number_season_number_level_key', type_='unique')
        batch_op.create_unique_constraint('_year_month_league_season_level_uc', ['year', 'month', 'league_number', 'season_number', 'level'])

    with op.batch_alter_table('names_in_teams', schema=None) as batch_op:
        batch_op.drop_constraint('names_in_teams_team_id_first_name_middle_name_last_name_key', type_='unique')
        batch_op.create_unique_constraint('_team_name_uc', ['team_id', 'first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('penalties', schema=None) as batch_op:
        batch_op.drop_constraint('penalties_game_id_team_id_penalty_sequence_number_key', type_='unique')
        batch_op.create_unique_constraint('_game_team_penalty_sequence_uc', ['game_id', 'team_id', 'penalty_sequence_number'])

    with op.batch_alter_table('referee_names', schema=None) as batch_op:
        batch_op.drop_constraint('referee_names_first_name_middle_name_last_name_key', type_='unique')
        batch_op.create_unique_constraint('_referee_name_uc', ['first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('scorekeeper_names', schema=None) as batch_op:
        batch_op.drop_constraint('scorekeeper_names_first_name_middle_name_last_name_key', type_='unique')
        batch_op.create_unique_constraint('_scorekeeper_name_uc', ['first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.drop_constraint('seasons_league_number_season_number_key', type_='unique')
        batch_op.create_unique_constraint('_league_season_uc', ['league_number', 'season_number'])

    with op.batch_alter_table('shootout', schema=None) as batch_op:
        batch_op.drop_constraint('shootout_game_id_shooting_team_id_sequence_number_key', type_='unique')
        batch_op.create_unique_constraint('_shootout_team_sequence_uc', ['game_id', 'shooting_team_id', 'sequence_number'])

    with op.batch_alter_table('teams_divisions', schema=None) as batch_op:
        batch_op.drop_constraint('teams_divisions_team_id_division_id_key', type_='unique')
        batch_op.create_unique_constraint('_team_division_uc', ['team_id', 'division_id'])

    with op.batch_alter_table('teams_in_tts', schema=None) as batch_op:
        batch_op.drop_constraint('teams_in_tts_team_id_tts_team_id_key', type_='unique')
        batch_op.create_unique_constraint('_team_tts_uc', ['team_id', 'tts_team_id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('teams_in_tts', schema=None) as batch_op:
        batch_op.drop_constraint('_team_tts_uc', type_='unique')
        batch_op.create_unique_constraint('teams_in_tts_team_id_tts_team_id_key', ['team_id', 'tts_team_id'])

    with op.batch_alter_table('teams_divisions', schema=None) as batch_op:
        batch_op.drop_constraint('_team_division_uc', type_='unique')
        batch_op.create_unique_constraint('teams_divisions_team_id_division_id_key', ['team_id', 'division_id'])

    with op.batch_alter_table('shootout', schema=None) as batch_op:
        batch_op.drop_constraint('_shootout_team_sequence_uc', type_='unique')
        batch_op.create_unique_constraint('shootout_game_id_shooting_team_id_sequence_number_key', ['game_id', 'shooting_team_id', 'sequence_number'])

    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.drop_constraint('_league_season_uc', type_='unique')
        batch_op.create_unique_constraint('seasons_league_number_season_number_key', ['league_number', 'season_number'])

    with op.batch_alter_table('scorekeeper_names', schema=None) as batch_op:
        batch_op.drop_constraint('_scorekeeper_name_uc', type_='unique')
        batch_op.create_unique_constraint('scorekeeper_names_first_name_middle_name_last_name_key', ['first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('referee_names', schema=None) as batch_op:
        batch_op.drop_constraint('_referee_name_uc', type_='unique')
        batch_op.create_unique_constraint('referee_names_first_name_middle_name_last_name_key', ['first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('penalties', schema=None) as batch_op:
        batch_op.drop_constraint('_game_team_penalty_sequence_uc', type_='unique')
        batch_op.create_unique_constraint('penalties_game_id_team_id_penalty_sequence_number_key', ['game_id', 'team_id', 'penalty_sequence_number'])

    with op.batch_alter_table('names_in_teams', schema=None) as batch_op:
        batch_op.drop_constraint('_team_name_uc', type_='unique')
        batch_op.create_unique_constraint('names_in_teams_team_id_first_name_middle_name_last_name_key', ['team_id', 'first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('levels_monthly', schema=None) as batch_op:
        batch_op.drop_constraint('_year_month_league_season_level_uc', type_='unique')
        batch_op.create_unique_constraint('levels_monthly_year_month_league_number_season_number_level_key', ['year', 'month', 'league_number', 'season_number', 'level'])

    with op.batch_alter_table('levels', schema=None) as batch_op:
        batch_op.drop_constraint('_level_name_uc', type_='unique')

    with op.batch_alter_table('humans_in_tts', schema=None) as batch_op:
        batch_op.drop_constraint('_human_tts_uc', type_='unique')
        batch_op.create_unique_constraint('humans_in_tts_human_id_tts_id_key', ['human_id', 'tts_id'])

    with op.batch_alter_table('humans_in_levels', schema=None) as batch_op:
        batch_op.drop_constraint('_levels_monthly_human_uc', type_='unique')
        batch_op.create_unique_constraint('humans_in_levels_levels_monthly_id_human_id_key', ['levels_monthly_id', 'human_id'])

    with op.batch_alter_table('humans', schema=None) as batch_op:
        batch_op.create_unique_constraint('humans_first_name_middle_name_last_name_key', ['first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('human_aliases', schema=None) as batch_op:
        batch_op.drop_constraint('_human_alias_uc', type_='unique')
        batch_op.create_unique_constraint('human_aliases_human_id_first_name_middle_name_last_name_key', ['human_id', 'first_name', 'middle_name', 'last_name'])

    with op.batch_alter_table('goals', schema=None) as batch_op:
        batch_op.drop_constraint('_goal_team_sequence_uc', type_='unique')
        batch_op.create_unique_constraint('goals_game_id_scoring_team_id_sequence_number_key', ['game_id', 'scoring_team_id', 'sequence_number'])

    with op.batch_alter_table('game_rosters', schema=None) as batch_op:
        batch_op.drop_constraint('_game_team_human_uc', type_='unique')
        batch_op.create_unique_constraint('game_rosters_game_id_team_id_human_id_key', ['game_id', 'team_id', 'human_id'])

    with op.batch_alter_table('divisions', schema=None) as batch_op:
        batch_op.create_unique_constraint('divisions_league_number_season_number_level_key', ['league_number', 'season_number', 'level'])
        batch_op.alter_column('season_number',
               existing_type=sa.INTEGER(),
               nullable=False)

    # ### end Alembic commands ###
