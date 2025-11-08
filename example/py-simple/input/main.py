# main.py

def func_c():
    print("in func_c")

def func_b():
    func_c()

def func_a():
    func_b()

def main():
    func_a()
    func_b()

if __name__ == "__main__":
    main()
