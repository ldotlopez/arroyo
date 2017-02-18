Arroyo
======

Arroyo is an automatic multimedia-multilingual download manager.



Install
=======

**You need python 3.4+**

* Download arroyo

    ```$ git clone https://bitbucket.org/ldotlopez/arroyo.git && cd "arroyo"```

* Create a python3 virtualenv (substitute virtualenv with whatever suits your system) and install python deps

    ```$ virtualenv -p python3 env && ./env/bin/pip install -r requirements.txt```

* Edit `arroyo.yml`

* Run `arroyo.sh`

    ``` $ ./arroyo.sh```


Basic usage
===========

Search:

```$ ./arroyo.sh search game of thrones s01e01```

Download:

```$ ./arroyo.sh download game of thrones s01e01```



How does it work
=============

Arroyo extracts the magnet links found in a set of user-defined URLs, analyzes and extracts information from them and stores them in a database.

Subsequently, based on a set of criteria defined by the user, selects the corresponding links and downloads them.

Arroyo recalls what material has been downloaded already (or it's in process) and is aware of the fact that several links may correspond to a single episode or movie. Thus avoiding downloading the same content twice. It also allows you to select the quality or language that you want.

In a way it is a cross between Couchpotato and SickBeard, adding multilingual support and multimedia (in the way it handles episodes, movies, music, books or anything).
