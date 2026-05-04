class FirstChoiceStrategy:
    def select_card(self, hand, game_state):
        return hand[0]

    def choose_effect(self, choices, game_state):
        return choices[0]

    def select_target(self, candidates, game_state):
        return candidates[0]

    def should_activate(self, card, game_state):
        return True


class LastChoiceStrategy(FirstChoiceStrategy):
    def select_target(self, candidates, game_state):
        return candidates[-1]
