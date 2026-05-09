from fuzzy_find import fuzzy_find


def main() -> None:
    options: list[str] = ['Java', 'JavaScript', 'Python', 'PHP', 'C++', 'Erlang', 'Haskell']
    option, index = fuzzy_find(options, title='Please choose your favorite programming language: ')
    print(option)
    print(index)


if __name__ == "__main__":
    main()
