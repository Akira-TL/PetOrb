import java.util.Properties

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://maven.aliyun.com/repository/public/") }
        maven { url = uri("https://jitpack.io") }

        val localCredentials = Properties()
        val credentialsFile = file("insta360.properties")
        if (credentialsFile.isFile) {
            credentialsFile.inputStream().use(localCredentials::load)
        }
        val instaUser = System.getenv("INSTA360_MAVEN_USERNAME") ?: localCredentials.getProperty("username")
        val instaPassword = System.getenv("INSTA360_MAVEN_PASSWORD") ?: localCredentials.getProperty("password")
        maven {
            url = uri("https://androidsdk.insta360.com/repository/maven-public/")
            if (!instaUser.isNullOrBlank() && !instaPassword.isNullOrBlank()) {
                credentials {
                    username = instaUser
                    password = instaPassword
                }
            }
        }
    }
}

rootProject.name = "PetOrbCameraBridge"
include(":app")
