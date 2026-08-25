"""Sample test: the one-vote-per-source cap is the invariant this project bets on."""

from wave_consensus.votes import Observation, Polarity, Vote, VoteMatrix


def make_obs(agent: str, prop: str, vote: Vote, polarity: Polarity = Polarity.POS) -> Observation:
    return Observation(agent=agent, proposition_id=prop, polarity=polarity, vote=vote)


def test_one_vote_per_source_caps_repeated_assertions():
    m = VoteMatrix()
    # Agent A asserts prop "p1" three times (verbosity), agent B once.
    for _ in range(3):
        m.add(make_obs("A", "p1", Vote.AFFIRM))
    m.add(make_obs("B", "p1", Vote.AFFIRM))

    # Unique-source support counts agents, not sentences: 2, not 4.
    assert m.unique_source_support("p1", Vote.AFFIRM) == 2
    assert sorted(m.supports("p1", Vote.AFFIRM)) == ["A", "B"]


def test_silence_is_an_explicit_state_not_a_missing_value():
    m = VoteMatrix()
    m.add(make_obs("A", "p1", Vote.AFFIRM))
    m.add(make_obs("B", "p1", Vote.DENY))
    # Agent C is silent on p1: cell is None, which the estimator reads as a
    # silence state under truth-dependent coverage, not a data gap.
    assert m.cell("p1", "C") is None
    assert m.unique_source_support("p1", Vote.DENY) == 1
    assert m.unique_source_support("p1", Vote.AFFIRM) == 1


def test_negative_polarity_is_first_class():
    m = VoteMatrix()
    m.add(make_obs("A", "n1", Vote.AFFIRM, polarity=Polarity.NEG))
    # The paper's NLI layer scored 0 of 607 negative-polarity propositions.
    # With structured output the negative cell must be present and countable.
    assert m.cell("n1", "A") is not None
    assert m.cell("n1", "A").polarity is Polarity.NEG
    assert m.unique_source_support("n1", Vote.AFFIRM) == 1


def test_instance_count_is_the_verbosity_weighted_ablation():
    m = VoteMatrix()
    m.add(make_obs("A", "p1", Vote.AFFIRM))
    m.add(make_obs("B", "p1", Vote.AFFIRM))
    instances = {("p1", "A"): 5, ("p1", "B"): 1}
    # Verbosity-weighted count is 6, unique-source count is 2.
    assert m.instance_count("p1", Vote.AFFIRM, instances) == 6
    assert m.unique_source_support("p1", Vote.AFFIRM) == 2
