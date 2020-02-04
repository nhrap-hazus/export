def main():
    import os
    print(os.getcwd())
    from src import app
    app = app()
    app.run_app()
    
if __name__ == "__main__":
    main()
