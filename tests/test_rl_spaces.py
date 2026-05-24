from flow_memory.rl.spaces import BoxSpace, DictSpace, DiscreteSpace

def test_discrete_and_dict_space_contains():
    space=DiscreteSpace(3, ("a","b","c"))
    assert space.contains(2)
    assert not space.contains(3)
    assert space.label(1) == "b"
    assert DictSpace(("x",)).contains({"x": 1})
    assert BoxSpace((2,), low=-1, high=1).contains([0, 0.5])
