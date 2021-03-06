import numpy as np
import math
import time
import matplotlib.pyplot as plt
import ray
import torch
from torch.autograd import Variable
from pysc2.lib import actions
from pysc2.lib import features
from pysc2.env import sc2_env

_NO_OP = actions.FUNCTIONS.no_op.id
_SELECT_POINT = actions.FUNCTIONS.select_point.id
_SELECT_ARMY = actions.FUNCTIONS.select_army.id
_SELECT_UNIT = actions.FUNCTIONS.select_unit.id
_ATTACK_SCREEN = actions.FUNCTIONS.Attack_screen.id
_MOVE_SCREEN = actions.FUNCTIONS.Move_screen.id
_MOVE_MINIMAP = actions.FUNCTIONS.Move_minimap.id

_PLAYER_RELATIVE = features.SCREEN_FEATURES.player_relative.index
_PLAYER_ID = features.SCREEN_FEATURES.player_id.index

_PLAYER_SELF = 1
_PLAYER_HOSTILE = 4

_UNIT_ALLIANCE = 1
_UNIT_HEALTH = 2
_UNIT_SHIELD = 3
_UNIT_X = 12
_UNIT_Y = 13
_UNIT_RADIUS = 15  # find range
_UNIT_HEALTH_RATIO = 7
_UNIT_IS_SELECTED = 17

_NOT_QUEUED = [0]
_QUEUED = [1]

ACTION_DO_NOTHING = 'donothing'
MOVE_UP = 'moveup'
MOVE_DOWN = 'movedown'
MOVE_LEFT = 'moveleft'
MOVE_RIGHT = 'moveright'

MOVE_UP_LEFT = 'moveupleft'
MOVE_UP_RIGHT = 'moveupright'
MOVE_DOWN_LEFT = 'movedownleft'
MOVE_DOWN_RIGHT = 'movedownright'

ACTION_SELECT_UNIT_1 = 'selectunit1'
ACTION_SELECT_UNIT_2 = 'selectunit2'
ATTACK_TARGET = 'attacktarget'

smart_actions = [
    # ACTION_DO_NOTHING,
    ATTACK_TARGET,
    MOVE_UP,
    MOVE_DOWN,
    MOVE_LEFT,
    MOVE_RIGHT,
    # MOVE_UP_LEFT,
    # MOVE_UP_RIGHT,
    # MOVE_DOWN_LEFT,
    # MOVE_DOWN_RIGHT,
    ACTION_SELECT_UNIT_1,
    ACTION_SELECT_UNIT_2
]
ENEMY_MAX_HP = 150
PLAYER_MAX_HP = 60
DEFAULT_ENEMY_COUNT = 4
DEFAULT_PLAYER_COUNT = 9


class SmartAgent(object):
    def __init__(self, net, epsilon):
        # from the origin base.agent
        self.reward = 0.0
        self.episodes = 0
        self.steps = 0
        self.epsilon = epsilon
        self.model = net
        # self defined vars
        self.fighting = False
        self.seperat_steps = 0
        self.win = 0
        self.player_hp = []
        self.player_hp_list = []
        self.enemy_hp = []
        self.enemy_hp_list = []
        self.reward_list = []
        self.previous_enemy_hp = []
        self.previous_player_hp = []

        self.previous_action = None
        self.previous_state = None

    def step(self, obs):
        # from the origin base.agent

        # time.sleep(0.5)
        current_state, enemy_hp, player_hp, enemy_loc, player_loc, distance, selected, enemy_count, player_count = self.extract_features(obs)

        while self.seperat_steps < 10:
            if selected[0] == 1 and selected[1] == 1:
                return -1, actions.FunctionCall(_SELECT_POINT, [_NOT_QUEUED, player_loc[0]]), -1, -1
            self.seperat_steps = self.seperat_steps + 1
            if MOVE_DOWN in obs.observation["available_actions"]:

                return -1, self.perform_action(obs, MOVE_DOWN, player_loc, enemy_loc, selected, enemy_count), -1, -1
            else:
                return -1, actions.FunctionCall(_NO_OP, []), -1, -1

        while not self.fighting:
            if selected[0] == 0 or selected[1] == 0:
                return -1, actions.FunctionCall(_SELECT_ARMY, [_NOT_QUEUED]), -1, -1
            for i in range(0, player_count):
                if distance[i] < 13:
                    self.fighting = True
                    return -1, actions.FunctionCall(_NO_OP, []), -1, -1
            if _MOVE_SCREEN in obs.observation["available_actions"]:

                return -1, actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, enemy_loc[0]]), -1, -1
            else:
                return -1, actions.FunctionCall(_NO_OP, []), -1, -1

        self.steps += 1
        # self.reward += obs.reward

        # if (self.steps % 10 == 0):
        #     self.player_hp_list.append(sum(player_hp))
        #     self.enemy_hp_list.append(sum(enemy_hp))

        # get the disabled actions and used it when choosing actions
        rl_action, actions_value = self.choose_action(np.array(current_state))
        smart_action = smart_actions[rl_action]
        # print(smart_action)
        if self.previous_action is not None:
            reward = self.get_reward(obs, distance, player_hp, enemy_hp, player_count, enemy_count, rl_action, selected,
                                     player_loc, enemy_loc)
        else:
            reward = 0
            # if (self.steps % 10 == 0):
            #     self.reward_list.append(reward)

        self.previous_state = current_state
        self.previous_action = rl_action
        self.previous_enemy_hp = enemy_hp
        self.previous_player_hp = player_hp

        return rl_action, self.perform_action(obs, smart_action, player_loc, enemy_loc, selected, enemy_count), actions_value, reward

    def choose_action(self, x):  # could use GPU
        x = Variable(torch.FloatTensor(x))
        action, actions_value = self.model.step(x)
        if np.random.uniform() > self.epsilon:
            action = np.random.randint(0, len(smart_actions))
        return action, actions_value

    def get_reward(self, obs, distance, player_hp, enemy_hp, player_count, enemy_count, rl_action, selected, unit_locs,
                   enemy_loc):
        reward = 0

        if (player_count == 0):
            return 0;
        # if smart_actions.index(ACTION_SELECT_UNIT_1) == rl_action and self.previous_action == rl_action:
        #     return -1
        # if smart_actions.index(ACTION_SELECT_UNIT_2) == rl_action and self.previous_action == rl_action:
        #     return -1

        closest_coor, unit_index = self.closest_unit(unit_locs, enemy_loc)

        index = -1

        for i in range(0, DEFAULT_PLAYER_COUNT):
            if selected[i] == 1:
                index = i

        # print("selected = ", index)
        # print("closest index = ", unit_index)
        # if (index == unit_index):
        #     reward += 2

        x = unit_locs[index][0]
        y = unit_locs[index][1]
        #
        # print("x = ", x)
        # print("y = ", y)
        # if (x < 5 and y < 5 and rl_action == smart_actions.index(MOVE_UP_LEFT)):
        #     return -1.5
        # if (x < 6 and y > 58 and rl_action == smart_action.index(MOVE_DOWN_LEFT)):
        #     return -1.5

        # if (x > 78 and y < 5 and rl_action == smart_action.index(MOVE_UP_RIGHT)):
        #     return -1.5
        # if (x > 78 and y > 58 and rl_action == smart_action.index(MOVE_DOWN_RIGHT)):
        #     return -1.5

        if ((x < 10 and rl_action == smart_actions.index(MOVE_LEFT))):
            return -1
        if ((x > 76 and rl_action == smart_actions.index(MOVE_RIGHT))):
            return -1
        if ((y < 9 and rl_action == smart_actions.index(MOVE_UP))):
            return -1
        if ((y > 56 and rl_action == smart_actions.index(MOVE_DOWN))):
            return -1

        # if (x < 15 and rl_action):
        #     return -0.5
        # if (x > 70 and rl_action):
        #     return -.5
        # if (y < 12 and rl_action):
        #     return -.5
        # if (y > 54 and rl_action):
        #     return -.5

        # pri_player_hp_sum = sum(self.previous_player_hp)
        # pri_enemy_hp_sum = sum(self.previous_enemy_hp)

        # player_hp_sum = sum(player_hp)
        # enemy_hp_sum = sum(enemy_hp)

        # print("pri_player_hp = ", pri_player_hp_sum)
        # print("pri_enemy_hp = ", pri_enemy_hp_sum)

        # print("player_hp = ", player_hp_sum)
        # print("enemy_hp = ", enemy_hp_sum)

        # print("distance = ", distance)

        # all_keep_dist = 0
        # for i in distance:
        #     if (i > 25 or i < 6):
        #         reward -= .5

        if distance[unit_index] < 10:
            return - 0.5

        if distance[unit_index] < 24:
            return 0.5

        # if all_keep_dist == 2:
        #     return 2
        # else:
        #     return -0.5
        # if player_hp_sum < pri_player_hp_sum:
        #     reward -= 1.5

        # if enemy_hp_sum < pri_enemy_hp_sum:
        #     reward += 2
        # reward += obs.reward
        return reward


    def extract_features(self, obs):

        var = obs.observation['feature_units']
        # get units' location and distance
        enemy, player = [], []

        # get health
        enemy_hp, player_hp = [], []

        # record the selected army
        is_selected = []

        # unit_count
        enemy_unit_count, player_unit_count = 0, 0

        for i in range(0, var.shape[0]):
            if var[i][_UNIT_ALLIANCE] == _PLAYER_HOSTILE:
                enemy.append((var[i][_UNIT_X], var[i][_UNIT_Y]))
                enemy_hp.append(var[i][_UNIT_HEALTH] + var[i][_UNIT_SHIELD])
                enemy_unit_count += 1
            else:
                player.append((var[i][_UNIT_X], var[i][_UNIT_Y]))
                player_hp.append(var[i][_UNIT_HEALTH])
                is_selected.append(var[i][_UNIT_IS_SELECTED])
                player_unit_count += 1

        # append if necessary
        for i in range(player_unit_count, DEFAULT_PLAYER_COUNT):
            player.append((-1, -1))
            player_hp.append(0)
            is_selected.append(-1)

        for i in range(enemy_unit_count, DEFAULT_ENEMY_COUNT):
            enemy.append((-1, -1))
            enemy_hp.append(0)

        # get distance
        min_distance = [100000 for x in range(DEFAULT_PLAYER_COUNT)]

        for i in range(0, player_unit_count):
            for j in range(0, enemy_unit_count):
                distance = int(math.sqrt((player[i][0] - enemy[j][0]) ** 2 + (
                        player[i][1] - enemy[j][1]) ** 2))

                if i < DEFAULT_PLAYER_COUNT and distance < min_distance[i]:
                    min_distance[i] = distance

        # flatten the array so that all features are a 1D array
        feature1 = np.array(enemy_hp).flatten()  # enemy's hp
        feature2 = np.array(player_hp).flatten()  # player's hp
        feature3 = np.array(enemy).flatten()  # enemy's coordinates
        feature4 = np.array(player).flatten()  # player's coordinates
        # feature5 = np.array(min_distance).flatten()  # distance

        closest_coor, unit_index = self.closest_unit(player, enemy)

        selecting_closest = []
        index = -1

        for i in range(0, DEFAULT_PLAYER_COUNT):
            if is_selected[i] == 1 and is_selected[1 - i] != 1:
                index = i
        if index == unit_index:
            selecting_closest.append(1)
        else:
            selecting_closest.append(0)

        # combine all features horizontally
        current_state = np.hstack((feature1, feature2, feature3, feature4, is_selected))
        # print("is_selected = ", is_selected)

        return current_state, feature1, feature2, enemy, player, min_distance, is_selected, enemy_unit_count, player_unit_count

    def calculate_distance(self, single_unit_coor, single_enemy_coor):
        dist = int(math.sqrt(
            (single_unit_coor[0] - single_enemy_coor[0]) ** 2 + (single_unit_coor[1] - single_enemy_coor[1]) ** 2))
        return dist;

    def closest_unit(self, unit_locs, enemy_locs):
        dist = 10000
        index = -1
        for i in range(0, 2):
            if self.calculate_distance(unit_locs[i], enemy_locs[0]) < dist:
                dist = self.calculate_distance(unit_locs[i], enemy_locs[0])
                index = i
        return unit_locs[i], index


    def perform_action(self, obs, action, unit_locs, enemy_locs, selected, enemy_count):

        closest_coor, unit_index = self.closest_unit(unit_locs, enemy_locs)

        other_unit_index = 0
        if unit_index == 1:
            other_unit_index = 0
        else:
            other_unit_index = 1


        unit_count = obs.observation['player'][8]

        index = -1

        for i in range(0, DEFAULT_PLAYER_COUNT):
            if selected[i] == 1:
                index = i

        x = unit_locs[index][0]
        y = unit_locs[index][1]

        if action == ACTION_SELECT_UNIT_1:
            if _SELECT_POINT in obs.observation['available_actions'] and unit_locs[unit_index] != (-1, -1):
                # print('1:',unit_locs[unit_index])
                # print("select closest")
                return actions.FunctionCall(_SELECT_POINT, [_NOT_QUEUED, unit_locs[unit_index]])

        elif action == ACTION_SELECT_UNIT_2:
            if _SELECT_POINT in obs.observation['available_actions'] and unit_locs[other_unit_index]!= (-1, -1):
                # print('2:',unit_locs[other_unit_index])
                # print("select farthest")
                return actions.FunctionCall(_SELECT_POINT, [_NOT_QUEUED, unit_locs[other_unit_index]])

        # -----------------------
        elif action == ATTACK_TARGET:
            if _ATTACK_SCREEN in obs.observation["available_actions"]:
                return actions.FunctionCall(_ATTACK_SCREEN, [_NOT_QUEUED, enemy_locs[0]])  # x,y => col,row
        # ------------------------
        # elif action == ACTION_DO_NOTHING:
        #     return actions.FunctionCall(_NO_OP, [])

        elif action == MOVE_UP:
            if _MOVE_SCREEN in obs.observation["available_actions"] and index != -1:
                x = x
                y = y - 10

                if 8 > x:
                    x = 8
                elif x > 80:
                    x = 80

                if 8 > y:
                    y = 8
                elif y > 60:
                    y = 60
                # print(action)
                return actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, [x, y]])  # x,y => col,row

        elif action == MOVE_DOWN:
            if _MOVE_SCREEN in obs.observation["available_actions"] and index != -1:
                x = x
                y = y + 10

                if 8 > x:
                    x = 8
                elif x > 80:
                    x = 80

                if 8 > y:
                    y = 8
                elif y > 60:
                    y = 60
                # print(action)
                return actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, [x, y]])

        elif action == MOVE_LEFT:
            if _MOVE_SCREEN in obs.observation["available_actions"] and index != -1:
                x = x - 10
                y = y

                if 8 > x:
                    x = 8
                elif x > 80:
                    x = 80

                if 8 > y:
                    y = 8
                elif y > 60:
                    y = 60
                # print(action)
                return actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, [x, y]])

        elif action == MOVE_RIGHT:
            if _MOVE_SCREEN in obs.observation["available_actions"] and index != -1:
                x = x + 10
                y = y

                if 8 > x:
                    x = 8
                elif x > 80:
                    x = 80

                if 8 > y:
                    y = 8
                elif y > 60:
                    y = 60
                # print(action)
                return actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, [x, y]])

        elif action == MOVE_UP_LEFT:
            x = x - 10
            y = y - 10

            if 8 > x:
                x = 8
            elif x > 80:
                x = 80

            if 8 > y:
                y = 8
            elif y > 60:
                y = 60
            # print(action)
            return actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, [x, y]])
        elif action == MOVE_UP_RIGHT:
            x = x + 10
            y = y - 10

            if 8 > x:
                x = 8
            elif x > 80:
                x = 80

            if 8 > y:
                y = 8
            elif y > 60:
                y = 60
            # print(action)
            return actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, [x, y]])

        elif action == MOVE_DOWN_LEFT:
            x = x - 10
            y = y + 10

            if 8 > x:
                x = 8
            elif x > 80:
                x = 80

            if 8 > y:
                y = 8
            elif y > 60:
                y = 60
            # print(action)
            return actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, [x, y]])
        elif action == MOVE_DOWN_RIGHT:
            x = x + 10
            y = y + 10

            if 8 > x:
                x = 8
            elif x > 80:
                x = 80

            if 8 > y:
                y = 8
            elif y > 60:
                y = 60
            # print(action)
            return actions.FunctionCall(_MOVE_SCREEN, [_NOT_QUEUED, [x, y]])

        self.previous_action = 5
        # print(action)
        return actions.FunctionCall(_NO_OP, [])

    # def plot_player_hp(self, path, save):
    #     plt.plot(np.arange(len(self.player_hp_list)), self.player_hp_list)
    #     plt.ylabel('player hp')
    #     plt.xlabel('training steps')
    #     if save:
    #         plt.savefig(path + '/player_hp.png')
    #     plt.show()
    #
    # def plot_enemy_hp(self, path, save):
    #     plt.plot(np.arange(len(self.enemy_hp_list)), self.enemy_hp_list)
    #     plt.ylabel('enemy hp')
    #     plt.xlabel('training steps')
    #     if save:
    #         plt.savefig(path + '/enemy_hp.png')
    #     plt.show()


    # from the origin base.agent
    def reset(self):
        self.episodes += 1
        # added instead of original
        self.fighting = False
        self.counter = 0
        self.seperat_steps = 0
        self.previous_player_hp = []

    # def plot_reward(self, path, save):
    #     plt.plot(np.arange(len(self.reward_list)), self.reward_list)
    #     plt.ylabel('Reward')
    #     plt.xlabel('training steps')
    #     if save:
    #         plt.savefig(path + '/reward.png')
    #     plt.show()

